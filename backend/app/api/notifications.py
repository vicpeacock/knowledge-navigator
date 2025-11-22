"""
API endpoints for notifications
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List, Optional
import asyncio
import json
import logging

from app.db.database import get_db
from app.services.notification_service import NotificationService
from app.models.schemas import Notification as NotificationSchema
from app.core.tenant_context import get_tenant_id
from app.core.user_context import get_current_user
from app.models.database import User

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=List[NotificationSchema])
async def get_notifications(
    session_id: Optional[UUID] = Query(None, description="Filter by session ID"),
    urgency: Optional[str] = Query(None, description="Filter by urgency (high, medium, low)"),
    read: bool = Query(False, description="Include read notifications"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Limit number of results"),
    offset: Optional[int] = Query(None, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """Get pending notifications (for current tenant and current user)"""
    notification_service = NotificationService(db)
    notifications = await notification_service.get_pending_notifications(
        session_id=session_id,
        urgency=urgency,
        read=read,
        tenant_id=tenant_id,
        limit=limit,
        offset=offset,
    )
    
    # Filter notifications for current user (same logic as in stream and sessions.py)
    from app.models.database import Integration
    from sqlalchemy import select
    
    # Pre-load integrations for current user
    user_integrations_result = await db.execute(
        select(Integration).where(
            Integration.tenant_id == tenant_id,
            Integration.user_id == current_user.id,
            Integration.enabled == True,
        )
    )
    user_integrations = {str(i.id): i for i in user_integrations_result.scalars().all()}
    
    integrations_without_user_id_result = await db.execute(
        select(Integration).where(
            Integration.tenant_id == tenant_id,
            Integration.user_id.is_(None),
            Integration.enabled == True,
        )
    )
    integrations_without_user_id = {str(i.id): i for i in integrations_without_user_id_result.scalars().all()}
    
    # Filter notifications for current user
    filtered_notifications = []
    for n in notifications:
        notif_type = n.get("type")
        content = n.get("content", {})
        
        if notif_type in ["email_received", "calendar_event_starting"]:
            notification_user_id = content.get("user_id")
            integration_id = content.get("integration_id")
            
            if notification_user_id:
                if str(notification_user_id) != str(current_user.id):
                    continue
            elif integration_id:
                integration_id_str = str(integration_id)
                if integration_id_str not in user_integrations and integration_id_str not in integrations_without_user_id:
                    continue
        filtered_notifications.append(n)
    
    return filtered_notifications


@router.get("/stream")
async def stream_notifications(
    request: Request,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """
    Server-Sent Events stream for real-time notifications.
    Sends notifications as they are created or updated.
    """
    async def event_generator():
        notification_service = NotificationService(db)
        last_count = 0
        
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info(f"Client disconnected from notification stream (user: {current_user.email})")
                    break
                
                # Get current notification count
                current_count = await notification_service.get_notification_count(
                    read=False,
                    tenant_id=tenant_id,
                )
                
                # If count changed, send update
                if current_count != last_count:
                    # Get latest notifications
                    notifications = await notification_service.get_pending_notifications(
                        read=False,
                        tenant_id=tenant_id,
                        limit=10,  # Send latest 10
                    )
                    
                    # Filter notifications for current user (same logic as in sessions.py)
                    from app.models.database import Integration
                    from sqlalchemy import select
                    
                    # Pre-load integrations (same optimization as in sessions.py)
                    user_integrations_result = await db.execute(
                        select(Integration).where(
                            Integration.tenant_id == tenant_id,
                            Integration.user_id == current_user.id,
                            Integration.enabled == True,
                        )
                    )
                    user_integrations = {str(i.id): i for i in user_integrations_result.scalars().all()}
                    
                    integrations_without_user_id_result = await db.execute(
                        select(Integration).where(
                            Integration.tenant_id == tenant_id,
                            Integration.user_id.is_(None),
                            Integration.enabled == True,
                        )
                    )
                    integrations_without_user_id = {str(i.id): i for i in integrations_without_user_id_result.scalars().all()}
                    
                    # Filter notifications for current user
                    filtered_notifications = []
                    for n in notifications:
                        notif_type = n.get("type")
                        content = n.get("content", {})
                        
                        if notif_type in ["email_received", "calendar_event_starting"]:
                            notification_user_id = content.get("user_id")
                            integration_id = content.get("integration_id")
                            
                            if notification_user_id:
                                if str(notification_user_id) != str(current_user.id):
                                    continue
                            elif integration_id:
                                integration_id_str = str(integration_id)
                                if integration_id_str not in user_integrations and integration_id_str not in integrations_without_user_id:
                                    continue
                        filtered_notifications.append(n)
                    
                    # Send update
                    data = {
                        "type": "notification_update",
                        "count": current_count,
                        "notifications": filtered_notifications,
                    }
                    yield f"data: {json.dumps(data)}\n\n"
                    last_count = current_count
                
                # Wait before next check
                await asyncio.sleep(2)  # Check every 2 seconds
                
        except asyncio.CancelledError:
            logger.info(f"Notification stream cancelled (user: {current_user.email})")
        except Exception as e:
            logger.error(f"Error in notification stream: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/count")
async def get_notification_count(
    session_id: Optional[UUID] = Query(None, description="Filter by session ID"),
    urgency: Optional[str] = Query(None, description="Filter by urgency (high, medium, low)"),
    read: bool = Query(False, description="Count read notifications"),
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Get count of notifications (for current tenant)"""
    notification_service = NotificationService(db)
    count = await notification_service.get_notification_count(
        session_id=session_id,
        urgency=urgency,
        read=read,
        tenant_id=tenant_id,
    )
    return {"count": count}


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Mark a notification as read (for current tenant)"""
    notification_service = NotificationService(db)
    success = await notification_service.mark_as_read(notification_id, tenant_id=tenant_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    return {"message": "Notification marked as read", "notification_id": str(notification_id)}


@router.post("/read-all")
async def mark_all_notifications_read(
    session_id: Optional[UUID] = Query(None, description="Filter by session ID"),
    urgency: Optional[str] = Query(None, description="Filter by urgency (high, medium, low)"),
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Mark all pending notifications as read (for current tenant)"""
    notification_service = NotificationService(db)
    count = await notification_service.mark_all_as_read(
        session_id=session_id,
        urgency=urgency,
        tenant_id=tenant_id,
    )
    return {"message": f"Marked {count} notifications as read", "count": count}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Delete a notification permanently (for current tenant)"""
    notification_service = NotificationService(db)
    success = await notification_service.delete_notification(notification_id, tenant_id=tenant_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    return {"message": "Notification deleted", "notification_id": str(notification_id)}


@router.post("/batch/delete")
async def delete_notifications_batch(
    notification_ids: List[UUID],
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Delete multiple notifications (for current tenant)"""
    notification_service = NotificationService(db)
    deleted_count = 0
    
    for notification_id in notification_ids:
        success = await notification_service.delete_notification(notification_id, tenant_id=tenant_id)
        if success:
            deleted_count += 1
    
    return {
        "message": f"Deleted {deleted_count} notifications",
        "deleted_count": deleted_count,
        "total_requested": len(notification_ids),
    }


@router.post("/check-events")
async def check_events_manual(
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """
    Manually trigger event check (email and calendar).
    Useful for testing proactive monitoring.
    """
    from app.services.event_monitor import EventMonitor
    
    event_monitor = EventMonitor()
    await event_monitor.check_once()
    
    # Get newly created notifications
    notification_service = NotificationService(db)
    notifications = await notification_service.get_pending_notifications(
        tenant_id=tenant_id,
        read=False,
    )
    
    return {
        "message": "Event check completed",
        "notifications_created": len(notifications),
        "notifications": notifications[:10],  # Return first 10
    }
