"""
API endpoints for notifications
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List, Optional

from app.db.database import get_db
from app.services.notification_service import NotificationService
from app.models.schemas import Notification as NotificationSchema
from app.core.tenant_context import get_tenant_id

router = APIRouter()


@router.get("/", response_model=List[NotificationSchema])
async def get_notifications(
    session_id: Optional[UUID] = Query(None, description="Filter by session ID"),
    urgency: Optional[str] = Query(None, description="Filter by urgency (high, medium, low)"),
    read: bool = Query(False, description="Include read notifications"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Limit number of results"),
    offset: Optional[int] = Query(None, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Get pending notifications (for current tenant)"""
    notification_service = NotificationService(db)
    notifications = await notification_service.get_pending_notifications(
        session_id=session_id,
        urgency=urgency,
        read=read,
        tenant_id=tenant_id,
        limit=limit,
        offset=offset,
    )
    return notifications


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

