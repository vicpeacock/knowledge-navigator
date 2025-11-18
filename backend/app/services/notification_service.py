"""
Notification Service - Manages proactive notifications from the assistant
"""
from typing import List, Dict, Any, Optional, Iterable, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from datetime import datetime, timezone
import logging

from app.models.database import Notification as NotificationModel

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing proactive notifications"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def notification_exists(
        self,
        type: str,
        content_key: str,
        content_value: str,
        tenant_id: Optional[UUID] = None,
        read: Optional[bool] = None,
        integration_id: Optional[str] = None,
    ) -> bool:
        """
        Check if a notification already exists based on type and content key-value.
        Useful for preventing duplicate notifications (e.g., same email_id or event_id).
        
        Args:
            type: Type of notification
            content_key: Key in content dict to check (e.g., "email_id", "event_id")
            content_value: Value to match
            tenant_id: Optional tenant ID to filter by
            read: Optional read status to filter by (None = any status)
            integration_id: Optional integration ID to filter by (for email/calendar notifications)
            
        Returns:
            True if notification exists, False otherwise
        """
        query = select(NotificationModel).where(
            NotificationModel.type == type,
            NotificationModel.content[content_key].astext == str(content_value)
        )
        
        if tenant_id:
            query = query.where(NotificationModel.tenant_id == tenant_id)
        
        if read is not None:
            query = query.where(NotificationModel.read == read)
        
        # For email/calendar notifications, also filter by integration_id if provided
        # This allows multiple integrations to process the same email/event independently
        if integration_id and type in ["email_received", "calendar_event_starting"]:
            query = query.where(
                NotificationModel.content["integration_id"].astext == str(integration_id)
            )
        
        result = await self.db.execute(query)
        existing = result.scalar_one_or_none()
        return existing is not None
    
    async def create_notification(
        self,
        type: str,  # "contradiction", "event", "todo", ecc.
        urgency: str,  # "high", "medium", "low"
        content: Dict[str, Any],
        session_id: Optional[UUID] = None,
        tenant_id: Optional[UUID] = None,
        check_duplicate: Optional[Dict[str, str]] = None,
    ) -> Optional[NotificationModel]:
        """
        Create a notification and save it to the database.
        
        Args:
            type: Type of notification (contradiction, event, todo, etc.)
            urgency: Urgency level (high, medium, low)
            content: Notification content (dict)
            session_id: Optional session ID if notification is related to a session
            tenant_id: Optional tenant ID
            check_duplicate: Optional dict with {"key": "content_key", "value": "content_value"}
                           to check if notification already exists before creating
            
        Returns:
            Created notification model, or None if duplicate check failed
        """
        # Check for duplicates if requested
        if check_duplicate:
            key = check_duplicate.get("key")
            value = check_duplicate.get("value")
            if key and value:
                # Extract integration_id from content if available (for email/calendar notifications)
                integration_id = content.get("integration_id") if isinstance(content, dict) else None
                
                exists = await self.notification_exists(
                    type=type,
                    content_key=key,
                    content_value=value,
                    tenant_id=tenant_id,
                    read=False,  # Only check unread notifications
                    integration_id=integration_id,  # Filter by integration_id for email/calendar
                )
                if exists:
                    logger.debug(
                        f"Skipping duplicate notification: type={type}, {key}={value}, integration_id={integration_id}"
                    )
                    return None
        
        notification = NotificationModel(
            type=type,
            urgency=urgency,
            content=content,
            session_id=session_id,
            tenant_id=tenant_id,
            read=False,
        )
        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)
        
        logger.info(f"Created notification: type={type}, urgency={urgency}, session_id={session_id}")
        return notification
    
    async def get_pending_notifications(
        self,
        session_id: Optional[UUID] = None,
        urgency: Optional[str] = None,
        read: bool = False,
        tenant_id: Optional[UUID] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get pending notifications.
        
        Args:
            session_id: Optional session ID to filter by
            urgency: Optional urgency level to filter by
            read: Whether to include read notifications (default: False, only unread)
            tenant_id: Optional tenant ID to filter by (required for multi-tenant)
            limit: Optional limit for pagination
            offset: Optional offset for pagination
            
        Returns:
            List of notification dicts
        """
        query = select(NotificationModel).where(NotificationModel.read == read)
        
        if tenant_id:
            query = query.where(NotificationModel.tenant_id == tenant_id)
        
        if session_id:
            query = query.where(NotificationModel.session_id == session_id)
        
        if urgency:
            query = query.where(NotificationModel.urgency == urgency)
        
        # Use composite index: order by created_at DESC (matches index)
        query = query.order_by(NotificationModel.created_at.desc())
        
        # Add pagination if provided
        if limit is not None:
            query = query.limit(limit)
        if offset is not None:
            query = query.offset(offset)
        
        result = await self.db.execute(query)
        notifications = result.scalars().all()
        
        return [
            {
                "id": str(notif.id),
                "type": notif.type,
                "urgency": notif.urgency,
                "content": notif.content,
                "session_id": str(notif.session_id) if notif.session_id else None,
                "read": notif.read,
                "created_at": notif.created_at.isoformat() if notif.created_at else None,
            }
            for notif in notifications
        ]
    
    async def mark_as_read(
        self,
        notification_id: Union[UUID, Iterable[UUID]],
        tenant_id: Optional[UUID] = None,
    ) -> bool:
        """
        Mark a notification as read.
        
        Args:
            notification_id: ID (or iterable of IDs) of the notification(s) to mark as read
            tenant_id: Optional tenant ID to filter by (required for multi-tenant)
            
        Returns:
            True if at least one notification was marked, False otherwise
        """
        if isinstance(notification_id, (list, tuple, set)):
            notification_ids = list(notification_id)
        else:
            notification_ids = [notification_id]
        
        if not notification_ids:
            return False
        
        query = select(NotificationModel).where(NotificationModel.id.in_(notification_ids))
        if tenant_id:
            query = query.where(NotificationModel.tenant_id == tenant_id)
        
        result = await self.db.execute(query)
        notifications = result.scalars().all()
        
        if not notifications:
            logger.warning(f"Notifications {notification_ids} not found")
            return False
        
        now = datetime.now(timezone.utc)
        for notification in notifications:
            notification.read = True
            notification.read_at = now
        
        await self.db.commit()
        
        logger.info(
            "Marked %d notification(s) as read: %s",
            len(notifications),
            [str(n.id) for n in notifications],
        )
        return True
    
    async def mark_all_as_read(
        self,
        session_id: Optional[UUID] = None,
        urgency: Optional[str] = None,
        tenant_id: Optional[UUID] = None,
    ) -> int:
        """
        Mark all pending notifications as read.
        
        Args:
            session_id: Optional session ID to filter by
            urgency: Optional urgency level to filter by
            tenant_id: Optional tenant ID to filter by (required for multi-tenant)
            
        Returns:
            Number of notifications marked as read
        """
        query = select(NotificationModel).where(NotificationModel.read == False)
        
        if tenant_id:
            query = query.where(NotificationModel.tenant_id == tenant_id)
        
        if session_id:
            query = query.where(NotificationModel.session_id == session_id)
        
        if urgency:
            query = query.where(NotificationModel.urgency == urgency)
        
        result = await self.db.execute(query)
        notifications = result.scalars().all()
        
        count = 0
        now = datetime.now(timezone.utc)
        for notif in notifications:
            notif.read = True
            notif.read_at = now
            count += 1
        
        if count > 0:
            await self.db.commit()
            logger.info(f"Marked {count} notifications as read")
        
        return count
    
    async def delete_notification(
        self,
        notification_id: UUID,
        tenant_id: Optional[UUID] = None,
    ) -> bool:
        """
        Delete a notification permanently.
        
        Args:
            notification_id: ID of the notification to delete
            tenant_id: Optional tenant ID to filter by (required for multi-tenant)
            
        Returns:
            True if notification was deleted, False otherwise
        """
        query = select(NotificationModel).where(NotificationModel.id == notification_id)
        if tenant_id:
            query = query.where(NotificationModel.tenant_id == tenant_id)
        
        result = await self.db.execute(query)
        notification = result.scalar_one_or_none()
        
        if not notification:
            logger.warning(f"Notification {notification_id} not found (tenant: {tenant_id})")
            return False
        
        # Delete the notification
        try:
            # Use delete statement for better reliability
            from sqlalchemy import delete as sql_delete
            delete_stmt = sql_delete(NotificationModel).where(
                NotificationModel.id == notification_id
            )
            if tenant_id:
                delete_stmt = delete_stmt.where(NotificationModel.tenant_id == tenant_id)
            
            result = await self.db.execute(delete_stmt)
            await self.db.commit()
            
            # Verify deletion
            if result.rowcount > 0:
                logger.info(f"✅ Successfully deleted notification {notification_id} (tenant: {tenant_id}, rowcount: {result.rowcount})")
                return True
            else:
                logger.warning(f"⚠️  Delete executed but no rows affected for notification {notification_id}")
                return False
        except Exception as e:
            logger.error(f"❌ Error deleting notification {notification_id}: {e}", exc_info=True)
            await self.db.rollback()
            raise
    
    async def get_notification_count(
        self,
        session_id: Optional[UUID] = None,
        urgency: Optional[str] = None,
        read: bool = False,
        tenant_id: Optional[UUID] = None,
    ) -> int:
        """
        Get count of notifications.
        
        Args:
            session_id: Optional session ID to filter by
            urgency: Optional urgency level to filter by
            read: Whether to count read notifications (default: False, only unread)
            tenant_id: Optional tenant ID to filter by (required for multi-tenant)
            
        Returns:
            Count of notifications
        """
        query = select(NotificationModel).where(NotificationModel.read == read)
        
        if tenant_id:
            query = query.where(NotificationModel.tenant_id == tenant_id)
        
        if session_id:
            query = query.where(NotificationModel.session_id == session_id)
        
        if urgency:
            query = query.where(NotificationModel.urgency == urgency)
        
        result = await self.db.execute(query)
        return len(result.scalars().all())

