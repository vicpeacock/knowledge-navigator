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
    
    async def create_notification(
        self,
        type: str,  # "contradiction", "event", "todo", ecc.
        urgency: str,  # "high", "medium", "low"
        content: Dict[str, Any],
        session_id: Optional[UUID] = None,
        tenant_id: Optional[UUID] = None,
    ) -> NotificationModel:
        """
        Create a notification and save it to the database.
        
        Args:
            type: Type of notification (contradiction, event, todo, etc.)
            urgency: Urgency level (high, medium, low)
            content: Notification content (dict)
            session_id: Optional session ID if notification is related to a session
            
        Returns:
            Created notification model
        """
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
    ) -> List[Dict[str, Any]]:
        """
        Get pending notifications.
        
        Args:
            session_id: Optional session ID to filter by
            urgency: Optional urgency level to filter by
            read: Whether to include read notifications (default: False, only unread)
            tenant_id: Optional tenant ID to filter by (required for multi-tenant)
            
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
        
        query = query.order_by(NotificationModel.created_at.desc())
        
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

