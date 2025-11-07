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

router = APIRouter()


@router.get("/", response_model=List[NotificationSchema])
async def get_notifications(
    session_id: Optional[UUID] = Query(None, description="Filter by session ID"),
    urgency: Optional[str] = Query(None, description="Filter by urgency (high, medium, low)"),
    read: bool = Query(False, description="Include read notifications"),
    db: AsyncSession = Depends(get_db),
):
    """Get pending notifications"""
    notification_service = NotificationService(db)
    notifications = await notification_service.get_pending_notifications(
        session_id=session_id,
        urgency=urgency,
        read=read,
    )
    return notifications


@router.get("/count")
async def get_notification_count(
    session_id: Optional[UUID] = Query(None, description="Filter by session ID"),
    urgency: Optional[str] = Query(None, description="Filter by urgency (high, medium, low)"),
    read: bool = Query(False, description="Count read notifications"),
    db: AsyncSession = Depends(get_db),
):
    """Get count of notifications"""
    notification_service = NotificationService(db)
    count = await notification_service.get_notification_count(
        session_id=session_id,
        urgency=urgency,
        read=read,
    )
    return {"count": count}


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Mark a notification as read"""
    notification_service = NotificationService(db)
    success = await notification_service.mark_as_read(notification_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    return {"message": "Notification marked as read", "notification_id": str(notification_id)}


@router.post("/read-all")
async def mark_all_notifications_read(
    session_id: Optional[UUID] = Query(None, description="Filter by session ID"),
    urgency: Optional[str] = Query(None, description="Filter by urgency (high, medium, low)"),
    db: AsyncSession = Depends(get_db),
):
    """Mark all pending notifications as read"""
    notification_service = NotificationService(db)
    count = await notification_service.mark_all_as_read(
        session_id=session_id,
        urgency=urgency,
    )
    return {"message": f"Marked {count} notifications as read", "count": count}

