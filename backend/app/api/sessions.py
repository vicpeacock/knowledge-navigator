import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from uuid import UUID
from typing import Any, Dict, List, Optional
from datetime import UTC, datetime, timedelta, timezone
import json as json_lib
import logging
import os
from fastapi.responses import StreamingResponse

from app.db.database import get_db
from app.models.database import Session as SessionModel, Message as MessageModel, User
from app.core.tenant_context import get_tenant_id
from app.core.user_context import get_current_user
from app.models.schemas import (
    Session,
    SessionCreate,
    SessionUpdate,
    Message,
    MessageCreate,
    ChatRequest,
    ChatResponse,
    MemoryInfo,
)
from app.core.dependencies import (
    get_ollama_client,
    get_memory_manager,
    get_planner_client,
    get_agent_activity_stream,
    get_background_task_manager,
)
from app.core.ollama_client import OllamaClient
from app.core.memory_manager import MemoryManager
from app.core.config import settings
from app.agents import run_langgraph_chat
from app.services.agent_activity_stream import AgentActivityStream
from app.services.background_task_manager import BackgroundTaskManager
from app.services.notification_service import NotificationService
from app.services.task_queue import TaskQueue, TaskStatus
from app.core.dependencies import get_task_queue

router = APIRouter()

logger = logging.getLogger(__name__)

_AGENT_LABELS: Dict[str, str] = {
    "event_handler": "Event Handler",
    "orchestrator": "Orchestrator",
    "tool_loop": "Tool Loop",
    "planner": "Planner",
    "knowledge_agent": "Knowledge Agent",
    "integrity_agent": "Integrity Agent",
    "notification_collector": "Notification Collector",
    "response_formatter": "Response Formatter",
    "background_integrity_agent": "Background Integrity Agent",
}

_FALLBACK_ACTIVITY_SEQUENCE: List[Dict[str, str]] = [
    {"agent_id": "event_handler", "status": "started"},
    {"agent_id": "event_handler", "status": "completed"},
    {"agent_id": "orchestrator", "status": "started"},
    {"agent_id": "orchestrator", "status": "completed"},
    {"agent_id": "tool_loop", "status": "started"},
    {"agent_id": "tool_loop", "status": "completed"},
    {"agent_id": "knowledge_agent", "status": "started"},
    {"agent_id": "knowledge_agent", "status": "completed"},
    {"agent_id": "integrity_agent", "status": "started"},
    {"agent_id": "integrity_agent", "status": "completed"},
    {"agent_id": "notification_collector", "status": "started"},
    {"agent_id": "notification_collector", "status": "completed"},
    {"agent_id": "response_formatter", "status": "started"},
    {"agent_id": "response_formatter", "status": "completed"},
]


def _normalize_agent_event(event: Any) -> Dict[str, Any]:
    if hasattr(event, "model_dump"):
        data: Dict[str, Any] = event.model_dump(mode="python")  # type: ignore[attr-defined]
    elif isinstance(event, dict):
        data = dict(event)
    else:
        return {}

    agent_id = data.get("agent_id", "unknown")
    data["agent_id"] = agent_id
    data["agent_name"] = data.get(
        "agent_name",
        _AGENT_LABELS.get(agent_id, agent_id.replace("_", " ").title()),
    )
    data["status"] = data.get("status", "completed")

    timestamp = data.get("timestamp")
    if isinstance(timestamp, str):
        try:
            data["timestamp"] = datetime.fromisoformat(timestamp)
        except ValueError:
            data["timestamp"] = datetime.now(UTC)
    elif not isinstance(timestamp, datetime):
        data["timestamp"] = datetime.now(UTC)

    return data


def _generate_fallback_agent_events() -> List[Dict[str, Any]]:
    base_time = datetime.now(UTC)
    events: List[Dict[str, Any]] = []
    for index, item in enumerate(_FALLBACK_ACTIVITY_SEQUENCE):
        event = {
            "agent_id": item["agent_id"],
            "agent_name": _AGENT_LABELS.get(
                item["agent_id"],
                item["agent_id"].replace("_", " ").title(),
            ),
            "status": item["status"],
            "timestamp": base_time + timedelta(milliseconds=75 * index),
        }
        events.append(event)
    return events


def _publish_agent_events(
    stream: AgentActivityStream, session_id: UUID, events: List[Dict[str, Any]]
) -> None:
    if not events:
        return
    for event in events:
        stream.publish(session_id, event)


@router.get("/", response_model=List[Session])
async def list_sessions(
    status: Optional[str] = None,  # Filter by status: active, archived, deleted
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """List all sessions for current user, optionally filtered by status"""
    # Filter by tenant_id AND user_id to ensure user isolation
    query = select(SessionModel).where(
        SessionModel.tenant_id == tenant_id,
        SessionModel.user_id == current_user.id
    )
    if status:
        query = query.where(SessionModel.status == status)
    query = query.order_by(SessionModel.updated_at.desc())
    result = await db.execute(query)
    sessions = result.scalars().all()
    # Map session_metadata to metadata for response
    return [
        Session(
            id=s.id,
            name=s.name,
            title=s.title,
            description=s.description,
            status=s.status,
            created_at=s.created_at,
            updated_at=s.updated_at,
            archived_at=s.archived_at,
            metadata=s.session_metadata or {},
        )
        for s in sessions
    ]


@router.post("/", response_model=Session, status_code=201)
async def create_session(
    session_data: SessionCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """Create a new session for current user"""
    session_dict = session_data.model_dump()
    # Map metadata to session_metadata for database model
    if 'metadata' in session_dict:
        metadata_value = session_dict.pop('metadata')
        session_dict['session_metadata'] = metadata_value
    # Assign tenant_id and user_id
    session_dict['tenant_id'] = tenant_id
    session_dict['user_id'] = current_user.id
    session = SessionModel(**session_dict)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    # Return response with metadata mapped back
    return Session(
        id=session.id,
        name=session.name,
        title=session.title,
        description=session.description,
        status=session.status,
        created_at=session.created_at,
        updated_at=session.updated_at,
        archived_at=session.archived_at,
        metadata=session.session_metadata or {},
    )


@router.get("/{session_id}", response_model=Session)
async def get_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """Get a session by ID (for current user or sessions created from integrations owned by current user)"""
    logger = logging.getLogger(__name__)
    
    # First check if session exists at all (for debugging)
    result_all = await db.execute(
        select(SessionModel).where(
            SessionModel.id == session_id,
            SessionModel.tenant_id == tenant_id,
        )
    )
    session_any_user = result_all.scalar_one_or_none()
    
    if not session_any_user:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Check if session belongs to current user
    if session_any_user.user_id == current_user.id:
        session = session_any_user
    else:
        # Session belongs to different user - check if it was created from an email integration
        # If so, verify that the email came from an integration owned by current user
        session_metadata = session_any_user.session_metadata or {}
        email_id = session_metadata.get("email_id")
        
        if email_id:
            # Check if there's an integration for this specific email that belongs to current user
            # We need to find which integration processed this email
            from app.models.database import Integration, Notification as NotificationModel
            from sqlalchemy import or_
            
            # First, try to find the notification for this email to get the integration_id
            notification_result = await db.execute(
                select(NotificationModel).where(
                    NotificationModel.tenant_id == tenant_id,
                    NotificationModel.type == "email_received",
                    NotificationModel.content["email_id"].astext == str(email_id),
                )
            )
            notification = notification_result.scalar_one_or_none()
            
            if notification:
                notification_content = notification.content if isinstance(notification.content, dict) else {}
                notification_integration_id = notification_content.get("integration_id")
                
                if notification_integration_id:
                    # Check if this integration belongs to current user
                    # First get the integration to see its user_id
                    integration_result = await db.execute(
                        select(Integration).where(
                            Integration.id == UUID(notification_integration_id),
                            Integration.tenant_id == tenant_id,
                        )
                    )
                    integration = integration_result.scalar_one_or_none()
                    
                    if integration:
                        logger.info(f"Found integration {notification_integration_id}: user_id={integration.user_id}, current_user.id={current_user.id}")
                        
                        if integration.user_id == current_user.id:
                            # Integration belongs to current user - allow access
                            logger.info(f"✅ Allowing access to session {session_id}: email came from integration {notification_integration_id} owned by current user")
                            session = session_any_user
                        else:
                            # Integration belongs to different user - check if current user has their own email integration
                            # If they do, this is a configuration issue (wrong integration was used)
                            # If they don't, they need to create their own integration
                            user_integrations_check = await db.execute(
                                select(Integration).where(
                                    Integration.tenant_id == tenant_id,
                                    Integration.provider == "google",
                                    Integration.service_type == "email",
                                    Integration.user_id == current_user.id,
                                    Integration.enabled == True,
                                )
                            )
                            user_has_integration = user_integrations_check.scalar_one_or_none() is not None
                            
                            if user_has_integration:
                                # User has their own integration - this is a bug: wrong integration was used
                                logger.error(f"❌ CONFIGURATION ISSUE: Session {session_id} created from email {email_id} via integration {notification_integration_id} which belongs to user {integration.user_id}, but current user {current_user.id} has their own email integration")
                                logger.error(f"   This indicates a bug: the email was processed by the wrong user's integration")
                                raise HTTPException(
                                    status_code=403, 
                                    detail=f"Session was created from an integration that belongs to a different user. Your account has its own email integration, but this email was processed by another user's integration. This is a configuration issue."
                                )
                            else:
                                # User doesn't have their own integration - they need to create one
                                logger.warning(f"⚠️  USER HAS NO INTEGRATION: Session {session_id} created from email {email_id} via integration {notification_integration_id} which belongs to user {integration.user_id}, but current user {current_user.id} has no email integration")
                                raise HTTPException(
                                    status_code=403, 
                                    detail=f"Session was created from an integration that belongs to a different user. You don't have an email integration configured. Please create your own Gmail integration in the Integrations page."
                                )
                    else:
                        logger.warning(f"Integration {notification_integration_id} not found")
                        raise HTTPException(status_code=403, detail="Session exists but integration not found")
                else:
                    # No integration_id in notification - check if user has any email integrations
                    user_integrations_result = await db.execute(
                        select(Integration).where(
                            Integration.tenant_id == tenant_id,
                            Integration.provider == "google",
                            Integration.service_type == "email",
                            Integration.user_id == current_user.id,
                            Integration.enabled == True,
                        )
                    )
                    if user_integrations_result.scalars().all():
                        logger.info(f"Allowing access to session {session_id}: current user has email integrations")
                        session = session_any_user
                    else:
                        raise HTTPException(status_code=403, detail="Session exists but you don't have access to it")
            else:
                # No notification found - check if user has email integrations
                user_integrations_result = await db.execute(
                    select(Integration).where(
                        Integration.tenant_id == tenant_id,
                        Integration.provider == "google",
                        Integration.service_type == "email",
                        Integration.user_id == current_user.id,
                        Integration.enabled == True,
                    )
                )
                if user_integrations_result.scalars().all():
                    logger.info(f"Allowing access to session {session_id}: current user has email integrations")
                    session = session_any_user
                else:
                    raise HTTPException(status_code=403, detail="Session exists but you don't have access to it")
        else:
            # Not an email-created session, require exact user match
            logger.warning(f"Session {session_id} belongs to user {session_any_user.user_id} but current user is {current_user.id}")
            raise HTTPException(
                status_code=403, 
                detail=f"Session exists but belongs to a different user (session user_id: {session_any_user.user_id}, your user_id: {current_user.id})"
            )
    
    # Map session_metadata to metadata for response
    return Session(
        id=session.id,
        name=session.name,
        title=session.title,
        description=session.description,
        status=session.status,
        created_at=session.created_at,
        updated_at=session.updated_at,
        archived_at=session.archived_at,
        metadata=session.session_metadata or {},
    )


@router.put("/{session_id}", response_model=Session)
async def update_session(
    session_id: UUID,
    session_data: SessionUpdate,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """Update a session (for current user)"""
    result = await db.execute(
        select(SessionModel).where(
            SessionModel.id == session_id,
            SessionModel.tenant_id == tenant_id,
            SessionModel.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    update_data = session_data.model_dump(exclude_unset=True)
    # Map metadata to session_metadata if present
    if 'metadata' in update_data:
        metadata_value = update_data.pop('metadata')
        update_data['session_metadata'] = metadata_value
    
    for key, value in update_data.items():
        setattr(session, key, value)
    
    await db.commit()
    await db.refresh(session)
    
    return Session(
        id=session.id,
        name=session.name,
        title=session.title,
        description=session.description,
        status=session.status,
        created_at=session.created_at,
        updated_at=session.updated_at,
        archived_at=session.archived_at,
        metadata=session.session_metadata or {},
    )


@router.post("/{session_id}/archive", response_model=Session)
async def archive_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    memory: MemoryManager = Depends(get_memory_manager),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """Archive a session and index it semantically in long-term memory (for current user)"""
    from datetime import datetime, timezone
    
    result = await db.execute(
        select(SessionModel).where(
            SessionModel.id == session_id,
            SessionModel.tenant_id == tenant_id,
            SessionModel.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session.status == "archived":
        raise HTTPException(status_code=400, detail="Session is already archived")
    
    # Update session status
    session.status = "archived"
    session.archived_at = datetime.now(timezone.utc)
    await db.commit()
    
    # Index session content semantically in long-term memory
    try:
        # Get all messages from the session
        messages_result = await db.execute(
            select(MessageModel)
            .where(MessageModel.session_id == session_id)
            .order_by(MessageModel.timestamp)
        )
        messages = messages_result.scalars().all()
        
        # Create a summary of the session
        session_content = f"Session: {session.title or session.name}\n"
        if session.description:
            session_content += f"Description: {session.description}\n"
        session_content += "\nConversation:\n"
        
        for msg in messages:
            session_content += f"{msg.role}: {msg.content}\n"
        
        # Store in long-term memory with high importance
        await memory.add_long_term_memory(
            db,
            content=session_content,
            learned_from_sessions=[session_id],
            importance_score=0.8,  # High importance for archived sessions
            tenant_id=session.tenant_id,
        )
        
        logger = logging.getLogger(__name__)
        logger.info(f"Session {session_id} archived and indexed in long-term memory")
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error indexing archived session: {e}", exc_info=True)
        # Don't fail the archive operation if indexing fails
    
    await db.refresh(session)
    return Session(
        id=session.id,
        name=session.name,
        title=session.title,
        description=session.description,
        status=session.status,
        created_at=session.created_at,
        updated_at=session.updated_at,
        archived_at=session.archived_at,
        metadata=session.session_metadata or {},
    )


@router.post("/{session_id}/restore", response_model=Session)
async def restore_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """Restore an archived session back to active (for current user)"""
    result = await db.execute(
        select(SessionModel).where(
            SessionModel.id == session_id,
            SessionModel.tenant_id == tenant_id,
            SessionModel.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session.status != "archived":
        raise HTTPException(status_code=400, detail="Session is not archived")
    
    session.status = "active"
    session.archived_at = None
    await db.commit()
    await db.refresh(session)
    
    return Session(
        id=session.id,
        name=session.name,
        title=session.title,
        description=session.description,
        status=session.status,
        created_at=session.created_at,
        updated_at=session.updated_at,
        archived_at=session.archived_at,
        metadata=session.session_metadata or {},
    )


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """Delete a session (soft delete by setting status to deleted) - for current user"""
    result = await db.execute(
        select(SessionModel).where(
            SessionModel.id == session_id,
            SessionModel.tenant_id == tenant_id,
            SessionModel.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Soft delete: set status to deleted instead of actually deleting
    session.status = "deleted"
    await db.commit()
    return None


@router.get("/{session_id}/messages", response_model=List[Message])
async def get_session_messages(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """Get all messages for a session (for current user)"""
    import logging
    logger = logging.getLogger(__name__)
    
    # First verify session belongs to user
    session_result = await db.execute(
        select(SessionModel).where(
            SessionModel.id == session_id,
            SessionModel.tenant_id == tenant_id,
            SessionModel.user_id == current_user.id
        )
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        result = await db.execute(
            select(MessageModel)
            .where(
                MessageModel.session_id == session_id,
                MessageModel.tenant_id == tenant_id
            )
            .order_by(MessageModel.timestamp)
        )
        messages = result.scalars().all()
        logger.info(f"Retrieved {len(messages)} messages for session {session_id}")
    except Exception as e:
        logger.error(f"Error retrieving messages: {e}", exc_info=True)
        raise
    # Map session_metadata to metadata for response
    result_messages = []
    for idx, m in enumerate(messages):
        try:
            # Convert session_metadata to dict if it's not already
            metadata = m.session_metadata
            
            # Handle different types of metadata - PostgreSQL JSONB can be tricky
            # JSONB columns can return different types depending on SQLAlchemy/PostgreSQL version
            if metadata is None:
                metadata = {}
            elif isinstance(metadata, dict):
                # Already a dict, ensure it's a plain Python dict (not a dict-like object)
                try:
                    # Create a new dict to ensure it's a plain Python dict
                    metadata = dict(metadata.items())
                except:
                    metadata = {}
            else:
                # For non-dict objects (like JSONB wrappers), use the most reliable approach
                original_type = type(metadata).__name__
                
                # Try multiple strategies to extract the actual dict value
                converted = False
                
                # Strategy 1: Check if it's a JSONB adapter and get the actual value
                # SQLAlchemy JSONB might wrap the value, try to unwrap it
                try:
                    # Some JSONB implementations expose the data via specific methods
                    if hasattr(metadata, 'asdict'):
                        metadata = metadata.asdict()
                        converted = True
                    elif hasattr(metadata, 'data'):
                        data_attr = getattr(metadata, 'data')
                        if isinstance(data_attr, dict):
                            metadata = dict(data_attr)
                            converted = True
                    elif hasattr(metadata, 'value'):
                        # Some wrappers use .value
                        value = getattr(metadata, 'value')
                        if isinstance(value, dict):
                            metadata = dict(value)
                            converted = True
                except Exception as e:
                    logger.debug(f"Strategy 1 failed: {e}")
                
                # Strategy 2: Use vars() or __dict__ if available
                if not converted:
                    try:
                        obj_dict = vars(metadata)
                        if isinstance(obj_dict, dict) and obj_dict:
                            # Check if there's a meaningful data attribute
                            if 'data' in obj_dict and isinstance(obj_dict['data'], dict):
                                metadata = dict(obj_dict['data'])
                                converted = True
                            elif len(obj_dict) > 0:
                                # If the dict itself has keys, it might be the data
                                metadata = {k: v for k, v in obj_dict.items() if not k.startswith('_')}
                                if metadata:
                                    converted = True
                    except Exception as e:
                        logger.debug(f"Strategy 2 failed: {e}")
                
                # Strategy 3: JSON serialization (may convert to string representation)
                if not converted:
                    try:
                        # Try with default=lambda o: o.__dict__ to preserve structure
                        json_str = json_lib.dumps(metadata, default=lambda o: vars(o) if hasattr(o, '__dict__') else str(o), ensure_ascii=False)
                        parsed = json_lib.loads(json_str)
                        if isinstance(parsed, dict):
                            metadata = parsed
                            converted = True
                    except Exception as e:
                        logger.debug(f"Strategy 3 failed: {e}")
                
                # Strategy 4: Force dict conversion (last resort)
                if not converted:
                    try:
                        if hasattr(metadata, 'items'):
                            metadata = dict(metadata.items())
                            converted = True
                        elif hasattr(metadata, '__iter__') and not isinstance(metadata, (str, bytes)):
                            # Only try if it's not a string
                            metadata = {}
                            converted = True  # Accept empty dict as conversion
                    except Exception as e:
                        logger.debug(f"Strategy 4 failed: {e}")
                
                # Final fallback: if nothing worked, use empty dict
                if not converted or not isinstance(metadata, dict):
                    logger.warning(f"Could not convert metadata from {original_type}, using empty dict. Repr: {repr(metadata)[:100]}")
                    metadata = {}
        
            result_messages.append(
                Message(
                    id=m.id,
                    session_id=m.session_id,
                    role=m.role,
                    content=m.content,
                    timestamp=m.timestamp,
                    metadata=metadata,
                )
            )
        except Exception as e:
            logger.error(f"Error processing message {idx} (id={m.id}): {e}", exc_info=True)
            # Still add the message but with empty metadata to avoid breaking the whole response
            try:
                result_messages.append(
                    Message(
                        id=m.id,
                        session_id=m.session_id,
                        role=m.role,
                        content=m.content,
                        timestamp=m.timestamp,
                        metadata={},
                    )
                )
            except Exception as e2:
                logger.error(f"Failed to add message even with empty metadata: {e2}", exc_info=True)
                raise
    
    logger.info(f"Returning {len(result_messages)} processed messages")
    return result_messages


# Notifications endpoints - placed early to avoid route conflicts
# IMPORTANT: Static routes must come before dynamic routes with path parameters
@router.delete("/notifications/contradictions", status_code=200)
async def clean_contradiction_notifications(
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Delete all pending notifications (all types) from the database for the current tenant"""
    logger = logging.getLogger(__name__)
    logger.info("🧹 Cleaning all pending notifications...")
    
    from app.models.database import Notification as NotificationModel
    
    # Count before deletion (filtered by tenant, only unread notifications)
    result = await db.execute(
        select(NotificationModel).where(
            NotificationModel.tenant_id == tenant_id,
            NotificationModel.read == False  # Only delete unread/pending notifications
        )
    )
    count_before = len(result.scalars().all())
    logger.info(f"📊 Found {count_before} pending notifications to delete for tenant {tenant_id}")
    
    if count_before == 0:
        logger.info("ℹ️  No pending notifications to delete")
        return {
            "message": "No pending notifications to delete",
            "deleted_count": 0
        }
    
    # Delete all pending notifications (filtered by tenant)
    try:
        delete_stmt = delete(NotificationModel).where(
            NotificationModel.tenant_id == tenant_id,
            NotificationModel.read == False  # Only delete unread/pending notifications
        )
        result = await db.execute(delete_stmt)
        rows_affected = result.rowcount if hasattr(result, 'rowcount') else count_before
        await db.commit()
        
        logger.info(f"✅ Deleted {count_before} pending notifications (rows affected: {rows_affected})")
        
        return {
            "message": f"Deleted {count_before} pending notifications",
            "deleted_count": count_before
        }
    except Exception as e:
        logger.error(f"❌ Error deleting pending notifications: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting pending notifications: {str(e)}"
        )


@router.get("/{session_id}/notifications/pending")
async def get_pending_notifications(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
    limit: Optional[int] = Query(100, ge=1, le=1000, description="Limit number of notifications"),
):
    """Get pending notifications that require user input (for current tenant and current user)"""
    import time
    start_time = time.time()
    logger = logging.getLogger(__name__)
    logger.info(f"📬 Fetching pending notifications for tenant {tenant_id}, user {current_user.id}, limit={limit}")
    import sys
    print(f"[NOTIFICATIONS] Starting fetch for session {session_id}, user {current_user.id}", file=sys.stderr)
    
    try:
        # Verify session belongs to tenant
        session_result = await db.execute(
            select(SessionModel).where(
                SessionModel.id == session_id,
                SessionModel.tenant_id == tenant_id
            )
        )
        if not session_result.scalar_one_or_none():
            logger.warning(f"❌ Session {session_id} not found for tenant {tenant_id}")
            raise HTTPException(status_code=404, detail="Session not found")
        
        service = NotificationService(db)
        # Add limit to avoid loading too many notifications
        notifications = await service.get_pending_notifications(read=False, tenant_id=tenant_id, limit=limit)
        
        logger.info(f"Found {len(notifications)} total pending notifications for tenant {tenant_id}")
        
        # OPTIMIZATION: Pre-load all integrations for this tenant/user once instead of querying per notification
        from app.models.database import Integration
        from sqlalchemy import or_
        
        # Get all integrations for current user (with user_id)
        user_integrations_result = await db.execute(
            select(Integration).where(
                Integration.tenant_id == tenant_id,
                Integration.user_id == current_user.id,
                Integration.enabled == True,
            )
        )
        user_integrations = {str(integration.id): integration for integration in user_integrations_result.scalars().all()}
        
        # Get all integrations without user_id for this tenant (for backward compatibility)
        integrations_without_user_id_result = await db.execute(
            select(Integration).where(
                Integration.tenant_id == tenant_id,
                Integration.user_id.is_(None),
                Integration.enabled == True,
            )
        )
        integrations_without_user_id = {str(integration.id): integration for integration in integrations_without_user_id_result.scalars().all()}
        
        # Collect all integration IDs from notifications to batch-load them
        integration_ids_to_check = set()
        for n in notifications:
            notif_type = n.get("type")
            if notif_type in ["email_received", "calendar_event_starting"]:
                integration_id = n.get("content", {}).get("integration_id")
                if integration_id and integration_id not in user_integrations and integration_id not in integrations_without_user_id:
                    try:
                        integration_ids_to_check.add(UUID(integration_id))
                    except:
                        pass
        
        # Batch-load missing integrations
        if integration_ids_to_check:
            missing_integrations_result = await db.execute(
                select(Integration).where(
                    Integration.id.in_(integration_ids_to_check),
                    Integration.tenant_id == tenant_id,
                )
            )
            for integration in missing_integrations_result.scalars().all():
                if integration.user_id == current_user.id:
                    user_integrations[str(integration.id)] = integration
                elif integration.user_id is None:
                    integrations_without_user_id[str(integration.id)] = integration
        
        # Cache: check if user has only one email integration (for heuristic)
        user_email_integrations = [
            i for i in user_integrations.values()
            if i.provider == "google" and i.service_type == "email"
        ]
        only_one_email_integration = len(user_email_integrations) == 1
        
        # Filter by type that requires user input AND by user_id (multi-tenant multi-user)
        global_notifications = []
        skipped_count = 0
        for n in notifications:
            notif_type = n.get("type")
            content = n.get("content", {})
            
            # For email_received and calendar_event_starting, filter by user_id
            # (each user should only see notifications from their own integrations)
            if notif_type in ["email_received", "calendar_event_starting"]:
                notification_user_id = content.get("user_id")
                integration_id = content.get("integration_id")
                
                if notification_user_id:
                    # Only show if notification belongs to current user
                    if str(notification_user_id) != str(current_user.id):
                        skipped_count += 1
                        continue
                elif integration_id:
                    # Check cached integrations
                    integration_id_str = str(integration_id)
                    
                    # Check if integration belongs to current user
                    if integration_id_str in user_integrations:
                        # Integration belongs to current user - allow notification
                        logger.debug(f"✅ Allowing notification {n.get('id')}: integration {integration_id} belongs to current user")
                    elif integration_id_str in integrations_without_user_id:
                        # Integration has no user_id - use heuristic
                        if only_one_email_integration and user_email_integrations[0].id == UUID(integration_id):
                            # User has only one email integration and it's this one - allow
                            logger.debug(f"✅ Allowing notification {n.get('id')}: integration {integration_id} is the only email integration for current user")
                        elif len(integrations_without_user_id) == 1 and list(integrations_without_user_id.values())[0].id == UUID(integration_id):
                            # Only one integration without user_id for tenant - allow
                            logger.debug(f"✅ Allowing notification {n.get('id')}: integration {integration_id} is the only integration without user_id")
                        else:
                            # Multiple integrations without user_id or user has multiple - skip
                            skipped_count += 1
                            continue
                    else:
                        # Integration not found or belongs to different user - skip
                        skipped_count += 1
                        continue
                else:
                    # No user_id and no integration_id - skip notification (can't verify ownership)
                    logger.info(f"⏭️  Skipping notification {n.get('id')}: no user_id or integration_id")
                    skipped_count += 1
                    continue
            
            # Return global notifications:
            # - contradiction: memory contradictions (visible to all users in tenant)
            # - email_received: new emails from proactivity system (filtered by user_id above)
            # - calendar_event_starting: upcoming calendar events (filtered by user_id above)
            if notif_type in ["contradiction", "email_received", "calendar_event_starting"]:
                global_notifications.append(n)
        
        logger.info(f"Found {len(global_notifications)} global notifications requiring user input (filtered for user {current_user.id}, skipped {skipped_count} notifications)")
        
        elapsed_time = time.time() - start_time
        logger.info(f"⏱️  Notification fetch completed in {elapsed_time:.2f}s: {len(global_notifications)} notifications")
        print(f"[NOTIFICATIONS] Fetch completed in {elapsed_time:.2f}s: {len(global_notifications)} notifications", file=sys.stderr)
        
        # Format for frontend
        result = []
        for notif in global_notifications:
            content = notif.get("content", {})
            created_at = notif.get("created_at")
            notif_type = notif.get("type")
            # Handle both datetime and string formats
            if created_at:
                if isinstance(created_at, str):
                    created_at_str = created_at
                else:
                    created_at_str = created_at.isoformat()
            else:
                created_at_str = None
                
            # Format content based on notification type
            formatted_content: Dict[str, Any] = {
                "message": content.get("message", ""),
                "title": content.get("title"),
            }
            
            # Add type-specific content
            if notif_type == "contradiction":
                formatted_content["new_statement"] = content.get("new_statement") or content.get("new_knowledge", {}).get("content") or content.get("new_knowledge", {}).get("text")
                formatted_content["contradictions"] = content.get("contradictions", [])
            elif notif_type == "email_received":
                # Include email-specific fields
                formatted_content["subject"] = content.get("subject")
                formatted_content["from"] = content.get("from")
                formatted_content["snippet"] = content.get("snippet")
                formatted_content["email_id"] = content.get("email_id")
                # Include auto_session_id if present (session created automatically from email analysis)
                auto_session_id = content.get("auto_session_id")
                if auto_session_id:
                    formatted_content["auto_session_id"] = auto_session_id
                    formatted_content["has_session"] = True
                # Also check session_id at notification level
                if notif.get("session_id"):
                    formatted_content["session_id"] = str(notif.get("session_id"))
                    if not formatted_content.get("has_session"):
                        formatted_content["has_session"] = True
                # Add session link if auto-created session exists
                session_id_for_link = auto_session_id or (str(notif.get("session_id")) if notif.get("session_id") else None)
                if session_id_for_link:
                    formatted_content["session_link"] = f"/sessions/{session_id_for_link}"
                # Create a user-friendly message if not present
                if not formatted_content["message"]:
                    subject = content.get("subject", "No Subject")
                    sender = content.get("from", "Unknown Sender")
                    formatted_content["message"] = f"Nuova email da {sender}: {subject}"
            elif notif_type == "calendar_event_starting":
                # Calendar notification content
                formatted_content["summary"] = content.get("summary")
                formatted_content["start_time"] = content.get("start_time")
                formatted_content["end_time"] = content.get("end_time")
                formatted_content["event_id"] = content.get("event_id")
                # Create a user-friendly message if not present
                if not formatted_content["message"]:
                    summary = content.get("summary", "Evento senza titolo")
                    start_time = content.get("start_time", "")
                    formatted_content["message"] = f"Evento imminente: {summary}" + (f" alle {start_time}" if start_time else "")
                
            result.append({
                "id": str(notif.get("id")),
                "type": notif_type,
                "priority": notif.get("urgency", "medium"),
                "created_at": created_at_str,
                "session_id": str(notif.get("session_id")) if notif.get("session_id") else None,
                "content": formatted_content,
            })
        
        total_time = time.time() - start_time
        logger.info(f"✅ Returning {len(result)} notifications in {total_time:.2f}s total")
        print(f"[NOTIFICATIONS] Returning {len(result)} notifications in {total_time:.2f}s", file=sys.stderr)
        return result
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"❌ Error fetching notifications after {elapsed_time:.2f}s: {e}", exc_info=True)
        print(f"[NOTIFICATIONS] ERROR after {elapsed_time:.2f}s: {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=f"Error fetching notifications: {str(e)}")


@router.post("/{session_id}/chat", response_model=ChatResponse)
async def chat(
    session_id: UUID,
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    ollama: OllamaClient = Depends(get_ollama_client),
    planner_client: OllamaClient = Depends(get_planner_client),
    memory: MemoryManager = Depends(get_memory_manager),
    agent_activity_stream: AgentActivityStream = Depends(get_agent_activity_stream),
    background_tasks: BackgroundTaskManager = Depends(get_background_task_manager),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    time_context = ""  # Initialize to avoid UnboundLocalError
    """Send a message and get AI response (for current user)"""
    # Log immediately at the start of the function - BEFORE any processing
    import sys
    import time
    start_time = time.time()
    try:
        print(f"[CHAT ENDPOINT] ===== CHAT REQUEST RECEIVED =====", file=sys.stderr, flush=True)
        print(f"[CHAT ENDPOINT] session_id={session_id}, message_length={len(request.message) if request else 'None'}, user={current_user.email if current_user else 'None'}", file=sys.stderr, flush=True)
        logger.info(f"📨📨📨 CHAT REQUEST RECEIVED: session_id={session_id}, message='{request.message[:100] if request and request.message else 'None'}', user={current_user.email if current_user else 'None'}")
        print(f"[SESSIONS] CHAT REQUEST: session_id={session_id}, message='{request.message[:100]}', user={current_user.email}", file=sys.stderr, flush=True)
    except Exception as log_error:
        # Even if logging fails, try to continue
        print(f"[CHAT ENDPOINT] ERROR in initial logging: {log_error}", file=sys.stderr, flush=True)
    
    # Check active SSE connections for this session
    active_sessions = agent_activity_stream.get_active_sessions()
    logger.debug(f"🔍 Active SSE sessions before chat: {len(active_sessions)} - {active_sessions}")
    print(f"[SESSIONS] Active SSE sessions: {len(active_sessions)} - {active_sessions}", file=sys.stderr)
    if session_id not in active_sessions:
        logger.warning(f"⚠️⚠️⚠️  Session {session_id} has NO active SSE connection! Telemetry events will not be delivered.")
        print(f"[SESSIONS] WARNING: Session {session_id} has NO active SSE connection!", file=sys.stderr)
    
    from app.core.dependencies import get_daily_session_manager
    
    # Check for day transition
    daily_session_manager = get_daily_session_manager(db)
    day_transition, new_session = await daily_session_manager.check_day_transition(
        user_id=current_user.id,
        tenant_id=tenant_id,
        current_session_id=session_id,
    )
    
    # If day transition occurred, require explicit confirmation via flag
    if day_transition and new_session:
        if not request.proceed_with_new_day:
            # Return a response indicating day transition that frontend will handle with a dialog
            logger.info(f"Day transition detected, returning special response for frontend dialog")
            return ChatResponse(
                response="",  # Empty response - frontend will show dialog
                session_id=session_id,
                memory_used={},
                tools_used=[],
                notifications_count=0,
                high_urgency_notifications=[],
                agent_activity=[],
                day_transition_pending=True,  # Signal to frontend
                new_session_id=str(new_session.id),
            )
        else:
            # User confirmed via dialog, use new session
            logger.info(f"User confirmed day transition via dialog, switching to new session {new_session.id}")
            session_id = new_session.id
            session = new_session
    else:
        # Verify session exists and belongs to user
        result = await db.execute(
            select(SessionModel).where(
                SessionModel.id == session_id,
                SessionModel.tenant_id == tenant_id,
                SessionModel.user_id == current_user.id
            )
        )
        session = result.scalar_one_or_none()
        
        if not session:
            # Session not found - try to get or create today's session
            logger.info(f"Session {session_id} not found, using today's daily session")
            session, _ = await daily_session_manager.get_or_create_today_session(
                user_id=current_user.id,
                tenant_id=tenant_id,
            )
            session_id = session.id
    
    # NOTE: Integrity contradiction check is now handled automatically by ConversationLearner
    # when new knowledge is indexed to long-term memory. We don't need to call it here for every message.
    # The scheduler will pick up any pending contradiction notifications and process them.
    
    # Get session context (previous messages) - filtered by tenant
    messages_result = await db.execute(
        select(MessageModel)
        .where(
            MessageModel.session_id == session_id,
            MessageModel.tenant_id == tenant_id
        )
        .order_by(MessageModel.timestamp)
    )
    previous_messages = messages_result.scalars().all()
    
    # Build context - ensure we're using plain dicts, not SQLAlchemy objects
    all_messages_dict = [
        {"role": str(msg.role), "content": str(msg.content)}
        for msg in previous_messages
    ]
    
    # Use conversation summarizer to optimize context if needed
    from app.services.conversation_summarizer import ConversationSummarizer
    summarizer = ConversationSummarizer(memory_manager=memory, ollama_client=ollama)
    
    # Retrieve memory if enabled (do this BEFORE optimizing context to consider it in size calculation)
    retrieved_memory = []
    memory_used = {"short_term": False, "medium_term": [], "long_term": [], "files": []}
    
    # Get the most recently uploaded file information from database
    from app.models.database import File as FileModel
    latest_file_result = await db.execute(
        select(FileModel)
        .where(FileModel.session_id == session_id)
        .order_by(FileModel.uploaded_at.desc())
        .limit(1)
    )
    latest_file = latest_file_result.scalar_one_or_none()
    
    # Always retrieve file content for the session (files are session-specific context)
    # Pass db to filter out embeddings for deleted files
    file_content = await memory.retrieve_file_content(
        session_id, request.message, n_results=5, db=db, tenant_id=tenant_id
    )
    memory_used["files"] = file_content
    
    # Add information about the most recent file to context
    file_context_info = []
    if latest_file:
        file_context_info.append(
            f"[IMPORTANT: File Information]\n"
            f"The most recently uploaded file in this session is:\n"
            f"- Filename: {latest_file.filename}\n"
            f"- Uploaded at: {latest_file.uploaded_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"- File ID: {latest_file.id}\n"
            f"When the user asks about 'the last file', 'the most recent file', 'the latest file', or 'ultimo file', they are referring to this file: {latest_file.filename}\n"
        )
    
    # Add file content to retrieved memory with clear labeling
    if file_content:
        logger.info(f"Retrieved {len(file_content)} file contents for session {session_id}")
        
        for i, content in enumerate(file_content):
            # Label file content clearly
            if content and content.strip():  # Only add non-empty content
                labeled_content = f"[Content from uploaded file {i+1}]:\n{content}"
                retrieved_memory.append(labeled_content)
                logger.info(f"Added file content {i+1}, length: {len(content)} chars")
            else:
                logger.warning(f"File content {i+1} is empty or None")
    else:
        logger.warning(f"No file content retrieved for session {session_id}")
    
    # Check if user explicitly requests a search - if so, don't use memory to force fresh search
    search_keywords = ["cerca", "search", "ricerca", "google scholar", "cerca su", "trova", "find", "lookup"]
    message_lower = request.message.lower()
    is_explicit_search_request = any(keyword in message_lower for keyword in search_keywords)
    
    if request.use_memory and not is_explicit_search_request:
        # Short-term memory
        short_term = await memory.get_short_term_memory(db, session_id)
        if short_term:
            memory_used["short_term"] = True
            # Extract tool_results from short-term memory if available
            tool_results_from_memory = short_term.get("tool_results", [])
            if tool_results_from_memory:
                # Add tool_results to retrieved_memory so they're available in context
                from app.agents.langgraph_app import _format_tool_results_for_llm
                tool_results_text = _format_tool_results_for_llm(tool_results_from_memory)
                retrieved_memory.insert(0, f"Risultati tool precedenti:\n{tool_results_text}")
        
        # Medium-term memory
        medium_mem = await memory.retrieve_medium_term_memory(
            session_id, request.message, n_results=3, tenant_id=tenant_id
        )
        memory_used["medium_term"] = medium_mem
        retrieved_memory.extend(medium_mem)
        
        # Long-term memory
        long_mem = await memory.retrieve_long_term_memory(
            request.message, n_results=3, tenant_id=tenant_id
        )
        memory_used["long_term"] = long_mem
        retrieved_memory.extend(long_mem)
    elif is_explicit_search_request:
        logger.info("🔍 Explicit search request detected - skipping memory retrieval to force fresh search")
        # Still get short-term memory for context, but skip medium/long-term that might contain old search results
        if request.use_memory:
            short_term = await memory.get_short_term_memory(db, session_id)
            if short_term:
                memory_used["short_term"] = True
                # Only add non-search-related short-term memory
                if isinstance(short_term, dict):
                    # Filter out search results from short-term memory
                    filtered_short_term = {k: v for k, v in short_term.items() 
                                         if not any(kw in str(v).lower() for kw in ["risultati ricerca", "search results", "google scholar"])}
                    if filtered_short_term:
                        retrieved_memory.append(str(filtered_short_term))
    
    # Add file context info to retrieved memory if available
    if file_context_info:
        retrieved_memory = file_context_info + retrieved_memory
    
    # Now get optimized context AFTER retrieving memory (to consider it in size calculation)
    session_context = await summarizer.get_optimized_context(
        db=db,
        session_id=session_id,
        all_messages=all_messages_dict,
        system_prompt="",  # Will be added by ollama client
        retrieved_memory=retrieved_memory,
        max_tokens=settings.max_context_tokens,
        keep_recent=settings.context_keep_recent_messages,
    )
    
    # Save user message
    user_message = MessageModel(
        session_id=session_id,
        tenant_id=tenant_id,
        role="user",
        content=request.message,
    )
    db.add(user_message)
    await db.commit()
    
    # Get current date/time and location for context
    from datetime import datetime
    import os  # Import os here to use os.environ
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        # Fallback for Python < 3.9
        try:
            from backports.zoneinfo import ZoneInfo
        except ImportError:
            ZoneInfo = None
    
    try:
        # Try to get timezone from environment or use Rome timezone
        tz_str = os.environ.get('TZ', 'Europe/Rome')  # Default to Italy
        
        if ZoneInfo:
            try:
                tz = ZoneInfo(tz_str)
            except:
                tz = ZoneInfo('Europe/Rome')  # Fallback to Italy
        else:
            # Fallback: use local time if zoneinfo not available
            tz = None
        
        current_time = datetime.now(tz) if tz else datetime.now()
        current_date = current_time.strftime('%A, %d %B %Y')  # e.g., "lunedì, 4 novembre 2024"
        current_time_str = current_time.strftime('%H:%M:%S')  # e.g., "16:30:45"
        timezone_name = tz_str.replace('_', ' ') if tz_str else 'local'
        
        # Get location info (can be configured via env)
        location = os.environ.get('USER_LOCATION', 'Italia')  # Default to Italy
        
        # Italian day names
        day_names = {
            'Monday': 'lunedì', 'Tuesday': 'martedì', 'Wednesday': 'mercoledì',
            'Thursday': 'giovedì', 'Friday': 'venerdì', 'Saturday': 'sabato', 'Sunday': 'domenica'
        }
        day_name = day_names.get(current_time.strftime('%A'), current_time.strftime('%A'))
        
        # Italian month names
        month_names = {
            'January': 'gennaio', 'February': 'febbraio', 'March': 'marzo',
            'April': 'aprile', 'May': 'maggio', 'June': 'giugno',
            'July': 'luglio', 'August': 'agosto', 'September': 'settembre',
            'October': 'ottobre', 'November': 'novembre', 'December': 'dicembre'
        }
        month_name = month_names.get(current_time.strftime('%B'), current_time.strftime('%B'))
        
        date_italian = f"{day_name}, {current_time.day} {month_name} {current_time.year}"
        
        time_context = f"""
=== CONTESTO TEMPORALE E GEOGRAFICO ===
Data e ora corrente: {date_italian}, {current_time_str} ({timezone_name})
Località: {location}
Giorno della settimana: {day_name}

=== REGOLE DI CONVERSAZIONE ===
- Se l'utente fa una DOMANDA, rispondi in modo completo e utile
- Se l'utente fa un'AFFERMAZIONE o fornisce informazioni SENZA fare domande, rispondi brevemente:
  * "Ok", "Perfetto", "Capito", "D'accordo" sono risposte appropriate
  * Non è necessario cercare sempre una risposta elaborata
  * Riconosci semplicemente l'informazione ricevuta
- Sii naturale e conversazionale - non essere verboso quando non necessario

"""

        
    except Exception as e:
        logger.warning(f"Error getting time context: {e}")
        time_context = ""
    

    # LangGraph branch
    logger.debug(f"🔍 Checking LangGraph flag: use_langgraph_prototype={settings.use_langgraph_prototype}")
    import sys
    print(f"[SESSIONS] LangGraph flag: {settings.use_langgraph_prototype}", file=sys.stderr)
    
    if settings.use_langgraph_prototype:
        logger.debug("✅ Using LangGraph pipeline")
        print(f"[SESSIONS] Using LangGraph pipeline", file=sys.stderr)
        existing_metadata = dict(session.session_metadata or {})
        pending_plan = existing_metadata.get("pending_plan")

        try:
            logger.debug("🚀 Calling run_langgraph_chat...")
            print(f"[SESSIONS] Calling run_langgraph_chat", file=sys.stderr)
            
            # Check if LLM client is available
            if ollama is None:
                raise HTTPException(
                    status_code=503,
                    detail="LLM client is not available. Please check your LLM provider configuration (Ollama/Gemini/Vertex AI)."
                )
            
            ollama._time_context = time_context
            langgraph_result = await run_langgraph_chat(
                db=db,
                session_id=session_id,
                request=request,
                ollama=ollama,
                planner_client=planner_client,
                agent_activity_stream=agent_activity_stream,
                memory_manager=memory,
                session_context=session_context,
                retrieved_memory=retrieved_memory,
                memory_used=memory_used,
                previous_messages=all_messages_dict,
                pending_plan=pending_plan,
                current_user=current_user,
            )
            logger.debug("✅ LangGraph completed successfully")
            print(f"[SESSIONS] LangGraph completed successfully", file=sys.stderr)
        except Exception as e:
            logger.error(f"❌❌❌ LangGraph failed with error: {e}", exc_info=True)
            print(f"[SESSIONS] LangGraph failed: {e}", file=sys.stderr)
            raise  # Re-raise to see the error

        # Debug: Log the result structure
        logger.debug(f"🔍 LangGraph result type: {type(langgraph_result)}")
        logger.debug(f"🔍 LangGraph result keys: {list(langgraph_result.keys()) if isinstance(langgraph_result, dict) else 'N/A'}")
        
        chat_response = langgraph_result["chat_response"]
        logger.debug(f"🔍 Chat response type: {type(chat_response)}")
        logger.debug(f"🔍 Chat response content: {chat_response.response[:100] if chat_response and chat_response.response else 'NONE'}")
        logger.debug(f"🔍 Chat response full length: {len(chat_response.response) if chat_response and chat_response.response else 0}")
        logger.debug(f"🔍 Assistant message saved flag: {langgraph_result.get('assistant_message_saved', False)}")
        
        new_plan_metadata = langgraph_result.get("plan_metadata")

        if new_plan_metadata:
            existing_metadata["pending_plan"] = new_plan_metadata
        else:
            existing_metadata.pop("pending_plan", None)

        session.session_metadata = existing_metadata

        # CRITICAL: Save assistant message to database BEFORE returning response to frontend
        # This ensures that if the HTTP response fails or times out, the message is still
        # available when the frontend reloads messages from the database
        if not langgraph_result.get("assistant_message_saved", False):
            assistant_message = MessageModel(
                session_id=session_id,
                tenant_id=tenant_id,
                role="assistant",
                content=chat_response.response,
                session_metadata={
                    "memory_used": chat_response.memory_used,
                    "tools_used": chat_response.tools_used,
                },
            )
            db.add(assistant_message)

        # Commit MUST complete before returning response to ensure message is persisted
        try:
            print(f"[CHAT ENDPOINT] Committing assistant message to database...", file=sys.stderr, flush=True)
            await db.commit()
            await db.refresh(session)
            logger.info(f"✅ Assistant message saved to database for session {session_id}")
            print(f"[CHAT ENDPOINT] Assistant message committed successfully", file=sys.stderr, flush=True)
        except Exception as commit_error:
            logger.error(f"❌ Error committing assistant message to database: {commit_error}", exc_info=True)
            print(f"[CHAT ENDPOINT] ERROR committing: {commit_error}", file=sys.stderr, flush=True)
            await db.rollback()
            # CRITICAL: If commit fails, we still need to ensure the message is saved
            # Try one more time before returning
            try:
                db.add(assistant_message)
                await db.commit()
                logger.info(f"✅ Assistant message saved to database (retry) for session {session_id}")
            except Exception as retry_error:
                logger.error(f"❌ Retry commit also failed: {retry_error}", exc_info=True)
                await db.rollback()
                logger.warning("⚠️  Database commit failed, but returning response anyway")
        
        # Log before returning response
        elapsed = time.time() - start_time
        print(f"[CHAT ENDPOINT] Preparing response after {elapsed:.2f}s...", file=sys.stderr, flush=True)

        # Ensure response is not empty - if it is, provide a fallback message
        if not chat_response.response or not chat_response.response.strip():
            logger.warning("⚠️  Chat response is empty, providing fallback message")
            chat_response = chat_response.model_copy(
                update={
                    "response": "Mi dispiace, non sono riuscito a generare una risposta. Potresti riprovare?"
                }
            )

        agent_events = [
            normalized
            for evt in chat_response.agent_activity
            if (normalized := _normalize_agent_event(evt))
        ]
        if not agent_events:
            agent_events = _generate_fallback_agent_events()

        _publish_agent_events(agent_activity_stream, session_id, agent_events)

        final_response = chat_response.model_copy(update={"agent_activity": agent_events})
        
        # Log before returning to verify response is correct
        logger.info(f"📤 Returning ChatResponse to frontend:")
        logger.info(f"   Response length: {len(final_response.response) if final_response.response else 0}")
        logger.info(f"   Response preview: {final_response.response[:200] if final_response.response else 'EMPTY'}...")
        logger.info(f"   Tools used: {len(final_response.tools_used)}")
        logger.info(f"   Agent activity events: {len(final_response.agent_activity)}")
        print(f"[SESSIONS] Returning ChatResponse: response_length={len(final_response.response) if final_response.response else 0}", file=sys.stderr, flush=True)
        elapsed_total = time.time() - start_time
        print(f"[CHAT ENDPOINT] ===== CHAT REQUEST COMPLETED in {elapsed_total:.2f}s =====", file=sys.stderr, flush=True)
        
        return final_response
    
    # Initialize tool manager
    from app.core.tool_manager import ToolManager
    tool_manager = ToolManager(db=db, tenant_id=tenant_id)
    
    # Get tools for native Ollama tool calling
    available_tools = await tool_manager.get_available_tools(current_user=current_user)
    
    # Also get tools description for fallback/prompt-based approach
    tools_description = await tool_manager.get_tools_system_prompt()
    
    tools_used = []
    max_tool_iterations = 3  # Limit tool call iterations
    tool_iteration = 0
    
    # Tool calling loop: LLM can request tools, we execute them, then reinvoke LLM with results
    current_prompt = request.message
    response_text = ""
    tool_results = []
    response_data = None  # Initialize to avoid undefined variable
    tool_calls = []  # Initialize to avoid UnboundLocalError when force_web_search is used
    
    import os
    
    while tool_iteration < max_tool_iterations:
        logger.info(f"Tool calling iteration {tool_iteration}, prompt length: {len(current_prompt)}")
        
        # Note: force_web_search is deprecated - tools are now managed via user preferences
        # If web_search is not in available_tools (user disabled it), it won't be available
        # We no longer force web_search here - let Ollama choose from available tools
        
        iteration_tool_results = []
        
        # Generate response with tools available
        if not iteration_tool_results:
            try:
                # Use native tool calling if tools are available, otherwise fallback to prompt-based
                pass_tools = available_tools if tool_iteration == 0 else None
                pass_tools_description = tools_description if tool_iteration == 0 and not available_tools else None
                
                # Check if LLM client is available
                if ollama is None:
                    raise HTTPException(
                        status_code=503,
                        detail="LLM client is not available. Please check your LLM provider configuration (Ollama/Gemini/Vertex AI)."
                    )
                
                # Add time context to ollama client
                ollama._time_context = time_context
                
                enhanced_prompt = current_prompt
                
                response_data = await ollama.generate_with_context(
                    prompt=enhanced_prompt,
                    session_context=session_context,
                    retrieved_memory=retrieved_memory if retrieved_memory else None,
                    tools=pass_tools,
                    tools_description=pass_tools_description,
                    return_raw=True,
                )
                
                # Handle both string response (old) and dict response (new with tool_calls)
                if isinstance(response_data, dict):
                    response_text = response_data.get("content", "")
                    ollama_tool_calls = response_data.get("_parsed_tool_calls")
                    if ollama_tool_calls:
                        logger.info(f"Ollama returned {len(ollama_tool_calls)} tool_calls in response structure")
                    # Debug: log the structure if content is empty
                    if not response_text and not ollama_tool_calls:
                        raw_result = response_data.get("raw_result", {})
                        logger.warning(f"Empty content and no tool_calls. Raw result keys: {list(raw_result.keys())}")
                        if "message" in raw_result:
                            msg = raw_result["message"]
                            logger.warning(f"Message structure: {type(msg)}, keys: {list(msg.keys()) if isinstance(msg, dict) else 'N/A'}")
                else:
                    response_text = response_data if response_data else ""
                    if not response_text:
                        logger.warning(f"Response_data is not a dict and empty. Type: {type(response_data)}")
                
                logger.info(f"Ollama response received, length: {len(response_text) if response_text else 0}, has content: {bool(response_text and response_text.strip())}")
            except Exception as e:
                logger.error(f"Error calling Ollama: {e}", exc_info=True)
                response_text = f"Errore nella chiamata al modello: {str(e)}"
                response_data = None
                break
            
            # Check if we have tool_calls first (before checking if content is empty)
            # This is important because tool_calls might mean empty content is OK
            has_tool_calls_in_response = False
            if response_data and isinstance(response_data, dict):
                parsed_tc = response_data.get("_parsed_tool_calls")
                raw_result = response_data.get("raw_result", {})
                if parsed_tc or (raw_result.get("message", {}).get("tool_calls")):
                    has_tool_calls_in_response = True
            
            if not response_text or not response_text.strip():
                if has_tool_calls_in_response:
                    logger.info("Content is empty but tool_calls present, continuing...")
                    # Set empty string - we'll generate response after tool execution
                    response_text = ""
                else:
                    logger.error(f"Empty response from Ollama on iteration {tool_iteration} and no tool_calls. Response_data type: {type(response_data)}")
                    if response_data and isinstance(response_data, dict):
                        logger.error(f"Response_data dict keys: {list(response_data.keys())}")
                        raw_result = response_data.get('raw_result', {})
                        if raw_result:
                            msg = raw_result.get('message', {})
                            if isinstance(msg, dict):
                                logger.error(f"Message keys: {list(msg.keys())}")
                                logger.error(f"Message content: '{msg.get('content', 'NOT FOUND')}'")
                                logger.error(f"Message thinking: '{msg.get('thinking', 'NOT FOUND')[:200] if msg.get('thinking') else 'N/A'}'")
                    # Return error immediately - don't continue loop if content is empty and no tool calls
                    response_text = "Mi scuso, ho riscontrato un problema nella generazione della risposta. Per favore riprova."
                    break
            
            # Check if LLM requested a tool call
            # First check if Ollama returned tool_calls in response structure
            tool_calls = []
            if response_data and isinstance(response_data, dict):
                # Check if we already have parsed tool calls from ollama_client
                parsed_tc = response_data.get("_parsed_tool_calls")
                if parsed_tc:
                    # Already parsed in ollama_client
                    tool_calls = parsed_tc
                    logger.info(f"✅ LLM automatically called {len(tool_calls)} tool(s): {[tc.get('name') for tc in tool_calls]}")
                else:
                    # Fallback: try to parse from raw tool_calls structure (shouldn't be needed with native tool calling)
                    raw_result = response_data.get("raw_result", {})
                    if "message" in raw_result and isinstance(raw_result["message"], dict):
                        message = raw_result["message"]
                        if "tool_calls" in message:
                            ollama_tc = message["tool_calls"]
                            # Standard Ollama format: {"function": {"name": "...", "arguments": {...}}}
                            for tc in ollama_tc:
                                if "function" in tc:
                                    func = tc["function"]
                                    func_name = func.get("name", "")
                                    func_args = func.get("arguments", {})
                                    
                                    # Parse arguments if string
                                    if isinstance(func_args, str):
                                        try:
                                            func_args = json_lib.loads(func_args)
                                        except json_lib.JSONDecodeError:
                                            logger.warning(f"Could not parse tool arguments: {func_args}")
                                            continue
                                    
                                    if func_name and isinstance(func_args, dict):
                                        tool_calls.append({
                                            "name": func_name,
                                            "parameters": func_args
                                        })
                            logger.info(f"Extracted {len(tool_calls)} tool calls from raw Ollama response")
            
            # Log what tools are available for debugging
            if tool_iteration == 0:
                # CRITICAL: Always pass current_user to respect user preferences
                available_tools = await tool_manager.get_available_tools(current_user=current_user)
                browser_tools = [t.get('name') for t in available_tools if 'browser' in t.get('name', '').lower()]
                logger.info(f"Available browser tools: {browser_tools}")
            
            # If response contains only JSON tool call, remove it for next iteration
            if tool_calls and response_text.strip().startswith('{'):
                # Response is likely only the JSON tool call
                logger.info("Response contains only tool call JSON, will regenerate after tool execution")
            
            if not tool_calls:
                # No tool calls, we have a normal response - use it
                # Make sure response_text doesn't contain leftover JSON
                if response_text and response_text.strip().startswith('{') and '"tool_call"' in response_text:
                    logger.warning("Response appears to be JSON but no tool calls parsed, attempting to clean")
                    # Try to extract any text after JSON
                    lines = response_text.split('\n')
                    text_only = [l for l in lines if not l.strip().startswith('{') and '}' not in l]
                    if text_only:
                        response_text = '\n'.join(text_only).strip()
                        logger.info(f"Cleaned response, new length: {len(response_text)}")
                    if not response_text:
                        logger.warning("Response cleaned to empty")
                # If we have content, use it; if empty, the check after the loop will handle it
                if response_text and response_text.strip():
                    logger.info(f"Using LLM response (no tools needed): {len(response_text)} chars")
                break
            
            # Execute tool calls (only if we don't already have results from force_web_search)
            if not iteration_tool_results:
                iteration_tool_results = []
                
                for tool_call in tool_calls:
                    tool_name = tool_call.get("name")
                    tool_params = tool_call.get("parameters", {})
                    
                    logger.info(f"Executing tool: {tool_name} with params: {tool_params}")
                    
                    if tool_name:
                        # Regular tool - execute it (including web_search and web_fetch)
                        # Note: web_search and web_fetch are NOT automatically executed by Ollama
                        # We must call the Ollama REST API ourselves when Ollama requests these tools
                        try:
                            result = await tool_manager.execute_tool(tool_name, tool_params, db, session_id=session_id)
                            logger.info(f"Tool {tool_name} executed successfully, result keys: {list(result.keys()) if isinstance(result, dict) else 'not a dict'}")
                            # Log result preview safely - avoid str() on very large dicts which can block
                            if isinstance(result, dict):
                                # Check if result has large content field without serializing entire dict
                                content_size = len(result.get('content', '')) if isinstance(result.get('content'), str) else 0
                                if content_size > 10000:
                                    logger.info(f"Tool {tool_name} result preview: Large result with {content_size} chars in content field, keys: {list(result.keys())}")
                                else:
                                    # Safe to serialize small dicts
                                    logger.info(f"Tool {tool_name} result preview: {str(result)[:500]}")
                            elif isinstance(result, str):
                                logger.info(f"Tool {tool_name} result preview: {result[:500]}")
                            else:
                                logger.info(f"Tool {tool_name} result type: {type(result)}")
                            iteration_tool_results.append({
                                "tool": tool_name,
                                "parameters": tool_params,  # Store parameters for detailed response
                                "result": result,
                            })
                            tools_used.append(tool_name)
                        except Exception as e:
                            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
                            iteration_tool_results.append({
                                "tool": tool_name,
                                "parameters": tool_params,
                                "result": {"error": str(e)},
                            })
        
        logger.info(f"Tool execution completed. iteration_tool_results count: {len(iteration_tool_results)}")
        
        # If tools were called, reinvoke LLM with results
        if iteration_tool_results:
            logger.info(f"Preparing to reinvoke LLM with {len(iteration_tool_results)} tool result(s)")
            # Format tool results for LLM
            tool_results_text = "\n\n=== Risultati Tool Chiamati ===\n"
            for tr in iteration_tool_results:
                tool_name = tr['tool']
                tool_results_text += f"Tool: {tool_name}\n"
                
                try:
                    # For browser results, extract content directly instead of JSON to preserve more information
                    # Note: tr['result'] has structure: {"success": True, "result": {...}, "tool": "..."}
                    wrapper_result = tr['result']
                    logger.debug(f"Formatting tool result for {tool_name}, wrapper_result type: {type(wrapper_result)}, keys: {list(wrapper_result.keys()) if isinstance(wrapper_result, dict) else 'N/A'}")
                    
                    if isinstance(wrapper_result, dict) and 'result' in wrapper_result:
                        # Unwrap the actual tool result
                        actual_result = wrapper_result.get('result', {})
                        logger.debug(f"actual_result type: {type(actual_result)}, keys: {list(actual_result.keys()) if isinstance(actual_result, dict) else 'N/A'}")
                        
                        # Check if we have formatted_text (for web_search/web_fetch) - use it directly
                        if isinstance(actual_result, dict) and 'formatted_text' in actual_result:
                            formatted_text = actual_result.get('formatted_text', '')
                            logger.info(f"Using formatted_text from tool {tool_name}, length: {len(formatted_text)}")
                            logger.debug(f"formatted_text preview (first 500 chars): {formatted_text[:500]}")
                            tool_results_text += f"{formatted_text}\n\n"
                        elif isinstance(actual_result, dict) and 'content' in actual_result:
                            # Browser tool returns content as string - use it directly instead of JSON
                            content = actual_result.get('content', '')
                            logger.info(f"Extracting content from browser tool result, content length: {len(content)}")
                            # Truncate to reasonable size but keep more than JSON would allow
                            if len(content) > 20000:
                                content = content[:20000] + "\n... [contenuto troncato per limiti di dimensione]"
                            tool_results_text += f"Risultato (contenuto pagina web):\n{content}\n\n"
                        else:
                            # Tool result doesn't have formatted_text or content field, use JSON format
                            logger.debug(f"actual_result doesn't have formatted_text or content field, using JSON format")
                            result_str = json_lib.dumps(wrapper_result, indent=2, ensure_ascii=False, default=str)
                            if len(result_str) > 15000:
                                result_str = result_str[:15000] + "\n... [risultato troncato]"
                            tool_results_text += f"Risultato: {result_str}\n\n"
                    else:
                        # For other tools or different structure, use JSON format
                        logger.debug(f"wrapper_result doesn't have 'result' key, using JSON format")
                        result_str = json_lib.dumps(wrapper_result, indent=2, ensure_ascii=False, default=str)
                        if len(result_str) > 15000:
                            result_str = result_str[:15000] + "\n... [risultato troncato]"
                        tool_results_text += f"Risultato: {result_str}\n\n"
                except Exception as e:
                    logger.error(f"Error formatting tool result for {tool_name}: {e}", exc_info=True)
                    tool_results_text += f"Risultato: [Errore nella formattazione del risultato: {str(e)}]\n\n"
            
            tool_results_text += "=== Fine Risultati Tool ===\n"
            tool_results_text += "IMPORTANTE: Usa SOLO i risultati dei tool sopra per rispondere. NON inventare informazioni.\n"
            tool_results_text += "Rispondi all'utente in modo naturale basandoti sui dati reali ottenuti.\n"
            
            # Update prompt with tool results and original question
            # Clear response_text since we'll regenerate with tool results
            response_text = ""
            
            # Regular tools - we have explicit results
            current_prompt = f"""L'utente ha chiesto: "{request.message}"

{tool_results_text}

Analizza i risultati dei tool sopra e rispondi all'utente in modo naturale e diretto basandoti sui dati ottenuti."""
            logger.info(f"Reinvoking LLM with tool results. Prompt length: {len(current_prompt)}")
            tool_results.extend(iteration_tool_results)
            
            # Call LLM with formatted tool results
            try:
                # Check if LLM client is available
                if ollama is None:
                    raise HTTPException(
                        status_code=503,
                        detail="LLM client is not available. Please check your LLM provider configuration (Ollama/Gemini/Vertex AI)."
                    )
                
                ollama._time_context = time_context
                response_data = await ollama.generate_with_context(
                    prompt=current_prompt,
                    session_context=session_context,
                    retrieved_memory=retrieved_memory if retrieved_memory else None,
                    tools=None,  # No tools on final response generation
                    tools_description=None,
                    return_raw=True,
                )
                
                # Extract response text
                if isinstance(response_data, dict):
                    response_text = response_data.get("content", "")
                else:
                    response_text = response_data if response_data else ""
                
                logger.info(f"LLM response generated from tool results, length: {len(response_text) if response_text else 0}")
                
                # Break after generating response
                if response_text and response_text.strip():
                    break
            except Exception as e:
                logger.error(f"Error calling LLM with tool results: {e}", exc_info=True)
                response_text = f"Errore nella generazione della risposta: {str(e)}"
                break
        else:
            # No tool results, break
            break
        
        tool_iteration += 1
    
    # Ensure response_text is never empty
    if not response_text or not response_text.strip():
        # Check if native Ollama tools were called
        native_tools_called = [t for t in tools_used if t in ["web_search", "web_fetch"]]
        if native_tools_called:
            logger.warning(f"Response text is empty after native Ollama tools were called: {native_tools_called}")
            logger.warning("This may mean Ollama is still processing the web search. Check if web search toggle is enabled in Ollama desktop app.")
            response_text = "Ho chiamato la ricerca web, ma non ho ricevuto risultati. Assicurati che la ricerca web sia abilitata nell'app desktop di Ollama (toggle attivo). Se il problema persiste, prova a riavviare Ollama o usa i tool MCP browser come alternativa."
        else:
            logger.error("Response text is empty after tool calling loop")
            response_text = "Mi scuso, ho riscontrato un problema nella generazione della risposta. Per favore riprova."
    
    # If we exhausted iterations and had tool calls, add note
    if tool_iteration >= max_tool_iterations and tool_calls and tool_results:
        response_text += "\n\n[Nota: Alcuni tool sono stati eseguiti per ottenere informazioni reali.]"
    
    # Check for pending notifications and format high urgency ones
    from app.services.notification_service import NotificationService
    notification_service = NotificationService(db)
    
    pending_notifications = await notification_service.get_pending_notifications(
        session_id=session_id,
        read=False,
    )
    
    # Group by urgency
    high_urgency = [n for n in pending_notifications if n.get("urgency") == "high"]
    medium_urgency = [n for n in pending_notifications if n.get("urgency") == "medium"]
    low_urgency = [n for n in pending_notifications if n.get("urgency") == "low"]
    
    # Format high urgency notifications for response (show immediately before response)
    formatted_high_notifications = []
    notification_prefix = ""
    
    if high_urgency:
        for notif in high_urgency:
            if notif.get("type") == "contradiction":
                content = notif.get("content", {})
                contradictions = content.get("contradictions", [])
                confidence = content.get("confidence", 0.0)
                
                if contradictions:
                    # Main decides notification urgency based on confidence and contradiction type
                    # High confidence (>0.8) = HIGH urgency, Medium (0.6-0.8) = MEDIUM, Low (<0.6) = LOW
                    final_urgency = "high"  # Default for contradictions
                    if confidence < 0.6:
                        final_urgency = "low"
                    elif confidence < 0.8:
                        final_urgency = "medium"
                    
                    logger.info(f"📋 Main decided notification urgency: {final_urgency} (confidence: {confidence:.2f})")
                    
                    # Format contradiction notification with Main's decision
                    formatted_high_notifications.append({
                        "type": "contradiction",
                        "urgency": final_urgency,  # Main's decision
                        "content": content,
                        "id": notif.get("id"),
                    })
    
    # NOTE: High urgency notifications are NOT prepended to response_text
    # They are sent separately in high_urgency_notifications field and displayed in StatusPanel
    # This prevents the LLM from including notification text in its response
    
    # Save assistant message
    # Log tools usage for debugging
    if tools_used:
        logger.info(f"Tools used in this response: {tools_used}")
    else:
        logger.info("No tools were used in this response")
    
    assistant_message = MessageModel(
        session_id=session_id,
        role="assistant",
        content=response_text,
        session_metadata={"memory_used": memory_used, "tools_used": tools_used},  # Store in metadata
    )
    db.add(assistant_message)
    await db.commit()

    # Update short-term memory with new context
    if request.use_memory:
        new_context = {
            "last_user_message": request.message,
            "last_assistant_message": response_text,
            "message_count": len(previous_messages) + 2,
        }
        await memory.update_short_term_memory(db, session_id, new_context, tenant_id=tenant_id)
        
        # Extract and index knowledge from conversation (auto-learning)
        # Run in background to avoid blocking the response
        try:
            from app.services.conversation_learner import ConversationLearner
            learner = ConversationLearner(memory_manager=memory, ollama_client=ollama)
            
            # Get recent conversation (last 10 messages including the new ones)
            recent_messages = [
                {"role": str(msg.role), "content": str(msg.content)}
                for msg in previous_messages[-8:]  # Last 8 previous + 2 new = 10 total
            ]
            recent_messages.append({"role": "user", "content": request.message})
            recent_messages.append({"role": "assistant", "content": response_text})
            
            # Extract knowledge (only if conversation has enough content)
            # Run asynchronously to not block the response
            # Reduced to 2 messages (1 exchange) to catch single statements like preferences
            if len(recent_messages) >= 2:  # At least 1 exchange (user + assistant)
                # Schedule for background execution (fire and forget)
                import asyncio
                from app.db.database import AsyncSessionLocal
                async def _extract_knowledge_background():
                    # Create a new database session for background task
                    async with AsyncSessionLocal() as db_session:
                        try:
                            logger.info(f"🔍 Extracting knowledge from {len(recent_messages)} messages")
                            knowledge_items = await learner.extract_knowledge_from_conversation(
                                db=db_session,
                                session_id=session_id,
                                messages=recent_messages,
                                min_importance=0.6,
                            )
                            
                            logger.info(f"Extracted {len(knowledge_items)} knowledge items from conversation")
                            if knowledge_items:
                                indexing_stats = await learner.index_extracted_knowledge(
                                    db=db_session,
                                    knowledge_items=knowledge_items,
                                    session_id=session_id,
                                )
                                logger.info(f"Auto-learned {indexing_stats.get('indexed', 0)} knowledge items from conversation")
                            else:
                                logger.info("⚠️ No knowledge items extracted (might be below importance threshold or not extractable)")
                        except Exception as e:
                            logger.warning(f"Error in background auto-learning: {e}", exc_info=True)
                
                # Schedule background task (don't await to avoid blocking)
                asyncio.create_task(_extract_knowledge_background())
            else:
                logger.info(f"⚠️ Skipping knowledge extraction: only {len(recent_messages)} messages (need at least 2)")
        except Exception as e:
            logger.warning(f"Error scheduling auto-learning from conversation: {e}", exc_info=True)

    # Build detailed tool execution information
    tool_details = []
    for tr in tool_results:
        tool_result = tr.get("result", {})
        
        # Determine success: check if result has "success" field, or if it has "error" field
        success = True
        error = None
        
        if isinstance(tool_result, dict):
            # Check for explicit success field (from tool_manager)
            if "success" in tool_result:
                success = tool_result.get("success", False)
            # Check for error field
            if "error" in tool_result:
                success = False
                error = tool_result.get("error")
            # Check if result itself is an error dict
            elif isinstance(tool_result.get("result"), dict) and "error" in tool_result.get("result", {}):
                success = False
                error = tool_result.get("result", {}).get("error")
        elif isinstance(tool_result, str):
            # If result is a string containing "error", it might be an error
            if "error" in tool_result.lower() and "error calling" in tool_result.lower():
                success = False
                error = tool_result
        
        tool_details.append({
            "tool_name": tr.get("tool", "unknown"),
            "parameters": tr.get("parameters", {}),
            "result": tool_result,
            "success": success,
            "error": error,
        })
    
    # Get notification count and high urgency notifications for response
    # (pending_notifications and formatted_high_notifications are already defined above)
    notification_count = len(pending_notifications) if 'pending_notifications' in locals() else 0
    high_urgency_notifs = formatted_high_notifications if 'formatted_high_notifications' in locals() else []
    
    # Return response
    agent_events = _generate_fallback_agent_events()
    _publish_agent_events(agent_activity_stream, session_id, agent_events)

    final_response = ChatResponse(
        response=response_text,
        session_id=session_id,
        memory_used=memory_used,
        tools_used=tools_used,
        tool_details=tool_details,
        notifications_count=notification_count,
        high_urgency_notifications=high_urgency_notifs,
        agent_activity=agent_events,
    )
    
    # Log before returning to verify response is correct (legacy path)
    logger.info(f"📤 Returning ChatResponse (legacy path) to frontend:")
    logger.info(f"   Response length: {len(final_response.response) if final_response.response else 0}")
    logger.info(f"   Response preview: {final_response.response[:200] if final_response.response else 'EMPTY'}...")
    logger.info(f"   Tools used: {len(final_response.tools_used)}")
    print(f"[SESSIONS] Returning ChatResponse (legacy): response_length={len(final_response.response) if final_response.response else 0}", file=sys.stderr)
    
    return final_response


@router.get("/{session_id}/agent-activity/stream")
async def stream_agent_activity(
    session_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    agent_activity_stream: AgentActivityStream = Depends(get_agent_activity_stream),
    tenant_id: UUID = Depends(get_tenant_id),
    token: Optional[str] = Query(None, description="JWT token for authentication (for SSE)"),
):
    """
    Server-Sent Events endpoint streaming real-time agent activity telemetry
    for the requested session.
    
    Note: EventSource doesn't support custom headers, so token is passed as query param.
    """
    import logging
    from app.core.user_context import get_current_user
    from app.core.auth import decode_token
    from sqlalchemy import select as sql_select
    
    logger = logging.getLogger(__name__)
    
    # Reduce logging verbosity for faster connection
    logger.debug(f"🔌 SSE connection request for session {session_id}")
    logger.debug(f"   Token provided: {bool(token)}, Tenant ID: {tenant_id}")

    # Get user from token (query param for SSE, or header for regular requests)
    # Optimize: Do minimal work before starting the stream
    current_user = None
    user_id_from_token = None
    
    if token:
        # Decode token from query parameter (fast, no DB query)
        payload = decode_token(token)
        if payload:
            user_id_from_token = payload.get("sub")
            logger.debug(f"   Token decoded, user_id: {user_id_from_token}")
    
    # Fallback to header if query param not provided
    authorization = None
    if not user_id_from_token:
        authorization = request.headers.get("Authorization")
        logger.debug(f"   Authorization header present: {bool(authorization)}")
    
    # Optimize: Run user lookup and session verification in parallel
    async def get_user():
        if user_id_from_token:
            try:
                user_uuid = UUID(str(user_id_from_token))
                # Only select id and email for faster query
                result = await db.execute(
                    sql_select(User.id, User.email, User.active).where(
                        User.id == user_uuid,
                        User.tenant_id == tenant_id,
                        User.active == True
                    )
                )
                user_row = result.first()
                if user_row:
                    # Create a minimal user object
                    from types import SimpleNamespace
                    user = SimpleNamespace()
                    user.id = user_row[0]
                    user.email = user_row[1]
                    user.active = user_row[2]
                    logger.debug(f"   ✅ User found: {user.email}")
                    return user
                else:
                    logger.debug(f"   ❌ User not found or inactive")
            except ValueError as e:
                logger.warning(f"   ❌ Invalid UUID format: {e}")
        elif authorization:
            try:
                user = await get_current_user(authorization=authorization, db=db, tenant_id=tenant_id)
                if user:
                    logger.debug(f"   ✅ User found via header: {user.email}")
                    return user
            except HTTPException as e:
                logger.debug(f"   ❌ Header auth failed: {e.detail}")
            except Exception as e:
                logger.debug(f"   ❌ Header auth error: {e}")
        return None
    
    async def verify_session(user_id: Optional[UUID]):
        if not user_id:
            return False
        # Only select id for faster query
        result = await db.execute(
            select(SessionModel.id).where(
                SessionModel.id == session_id,
                SessionModel.tenant_id == tenant_id,
                SessionModel.user_id == user_id
            )
        )
        return result.scalar_one_or_none() is not None
    
    # Get user first (needed for session verification)
    current_user = await get_user()
    
    if not current_user:
        logger.warning(f"❌ Unauthorized SSE connection attempt for session {session_id}")
        logger.warning(f"   Token was provided: {bool(token)}")
        logger.warning(f"   Authorization header present: {bool(authorization)}")
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Verify session exists and belongs to user (optimized query)
    session_exists = await verify_session(current_user.id)
    if not session_exists:
        logger.warning(f"❌ Session {session_id} not found for SSE stream")
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator():
        logger.info(f"✅ Starting SSE stream for session {session_id}")
        import sys
        print(f"[SSE] Starting stream for session {session_id}", file=sys.stderr)
        
        snapshot_payload = agent_activity_stream.snapshot_sse_payload(session_id)
        snapshot_events = agent_activity_stream.snapshot(session_id)
        if snapshot_payload:
            logger.info(f"📸 Sending snapshot with {len(snapshot_events)} events")
            print(f"[SSE] Sending snapshot with {len(snapshot_events)} events", file=sys.stderr)
            yield snapshot_payload
        else:
            logger.info(f"📸 No snapshot available (history empty)")
            print(f"[SSE] No snapshot available (history empty)", file=sys.stderr)

        queue = await agent_activity_stream.register(session_id)
        active_sessions = agent_activity_stream.get_active_sessions()
        logger.info(f"📡 Registered subscriber for session {session_id}, active sessions: {len(active_sessions)} - {active_sessions}")
        print(f"[SSE] Registered subscriber, active sessions: {len(active_sessions)} - {active_sessions}", file=sys.stderr)
        try:
            while True:
                if await request.is_disconnected():
                    logger.info(f"🔌 Client disconnected for session {session_id}")
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                    # event is a dict (serialized), not a Pydantic model
                    agent_id = event.get('agent_id', 'unknown') if isinstance(event, dict) else getattr(event, 'agent_id', 'unknown')
                    status = event.get('status', 'unknown') if isinstance(event, dict) else getattr(event, 'status', 'unknown')
                    logger.info(f"📨 Sending event to session {session_id}: {agent_id} ({status})")
                    import sys
                    print(f"[SSE] Sending event: {agent_id} ({status}) to session {session_id}", file=sys.stderr)
                    yield agent_activity_stream.as_sse_payload(event)
                except asyncio.TimeoutError:
                    continue
        finally:
            await agent_activity_stream.unregister(session_id, queue)
            logger.info(f"🔌 Unregistered subscriber for session {session_id}, active sessions: {len(agent_activity_stream.get_active_sessions())}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
        },
    )


@router.get("/{session_id}/agent-activity/debug")
async def debug_agent_activity(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    agent_activity_stream: AgentActivityStream = Depends(get_agent_activity_stream),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """Debug endpoint to check telemetry status for a session"""
    from sqlalchemy import select
    
    # Verify session belongs to user
    result = await db.execute(
        select(SessionModel).where(
            SessionModel.id == session_id,
            SessionModel.tenant_id == tenant_id,
            SessionModel.user_id == current_user.id
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Session not found")
    
    active_sessions = agent_activity_stream.get_active_sessions()
    history = agent_activity_stream.snapshot(session_id)
    
    return {
        "session_id": str(session_id),
        "has_active_sse_connection": session_id in active_sessions,
        "active_sessions_count": len(active_sessions),
        "active_sessions": [str(s) for s in active_sessions],
        "history_events_count": len(history),
        "recent_events": history[-10:] if history else [],
    }


@router.get("/{session_id}/memory", response_model=MemoryInfo)
async def get_session_memory(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    memory: MemoryManager = Depends(get_memory_manager),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """Get memory information for a session (for current user)"""
    logger = logging.getLogger(__name__)
    logger.info(f"📋 Getting memory info for session {session_id} (user: {current_user.email})")
    
    # Verify session belongs to user
    session_result = await db.execute(
        select(SessionModel).where(
            SessionModel.id == session_id,
            SessionModel.tenant_id == tenant_id,
            SessionModel.user_id == current_user.id
        )
    )
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get short-term memory (fast, from database)
    try:
        short_term = await memory.get_short_term_memory(db, session_id)
    except Exception as e:
        logger.warning(f"Error retrieving short-term memory: {e}")
        short_term = None
    
    # Get ALL long-term memories from database FIRST (fast, no ChromaDB)
    from app.models.database import MemoryLong as MemoryLongModel
    try:
        long_term_result = await db.execute(
            select(MemoryLongModel)
            .where(MemoryLongModel.tenant_id == tenant_id)
            .order_by(MemoryLongModel.created_at.desc())
        )
        all_long_term = long_term_result.scalars().all()
    except Exception as e:
        logger.warning(f"Error retrieving long-term memories from database: {e}")
        all_long_term = []
    
    # Get sample medium-term and long-term memories from ChromaDB in parallel with timeout
    import asyncio
    medium_samples = []
    long_samples = []
    
    async def get_medium_samples():
        try:
            return await asyncio.wait_for(
                memory.retrieve_medium_term_memory(
                    session_id, "sessione conversazione", n_results=5, tenant_id=tenant_id
                ),
                timeout=5.0  # 5 second timeout
            )
        except asyncio.TimeoutError:
            logger.warning("Timeout retrieving medium-term memory from ChromaDB")
            return []
        except Exception as e:
            logger.warning(f"Error retrieving medium-term memory: {e}")
            return []
    
    async def get_long_samples():
        try:
            return await asyncio.wait_for(
                memory.retrieve_long_term_memory(
                    "conoscenza apprendimento", n_results=5, tenant_id=tenant_id
                ),
                timeout=5.0  # 5 second timeout
            )
        except asyncio.TimeoutError:
            logger.warning("Timeout retrieving long-term memory samples from ChromaDB")
            return []
        except Exception as e:
            logger.warning(f"Error retrieving long-term memory samples: {e}")
            return []
    
    # Execute ChromaDB queries in parallel
    try:
        medium_samples, long_samples = await asyncio.gather(
            get_medium_samples(),
            get_long_samples(),
            return_exceptions=True
        )
        # Handle exceptions from gather
        if isinstance(medium_samples, Exception):
            logger.warning(f"Error in parallel medium-term retrieval: {medium_samples}")
            medium_samples = []
        if isinstance(long_samples, Exception):
            logger.warning(f"Error in parallel long-term retrieval: {long_samples}")
            long_samples = []
    except Exception as e:
        logger.warning(f"Error in parallel memory retrieval: {e}")
        medium_samples = []
        long_samples = []
    
    # Convert to schema format
    long_term_memories = []
    for mem in all_long_term:
        # Convert datetime to ISO string if needed
        created_at = mem.created_at
        if hasattr(created_at, 'isoformat'):
            created_at = created_at.isoformat()
        elif isinstance(created_at, str):
            created_at = created_at  # Already a string
        else:
            created_at = str(created_at)
        
        long_term_memories.append({
            "content": mem.content,
            "importance_score": mem.importance_score,
            "created_at": created_at,
            "learned_from_sessions": mem.learned_from_sessions or [],
        })
    
    # Count files
    from app.models.database import File as FileModel
    file_count_result = await db.execute(
        select(FileModel).where(FileModel.session_id == session_id)
    )
    files_count = len(file_count_result.scalars().all())
    
    # Count total messages
    from app.models.database import Message as MessageModel
    message_count_result = await db.execute(
        select(MessageModel).where(MessageModel.session_id == session_id)
    )
    total_messages = len(message_count_result.scalars().all())
    
    return MemoryInfo(
        short_term=short_term,
        medium_term_samples=medium_samples[:5],  # Limit to 5 samples
        long_term_samples=long_samples[:5],  # Limit to 5 samples (backward compatibility)
        long_term_memories=long_term_memories,  # All memories with full details
        files_count=files_count,
        total_messages=total_messages,
    )


@router.post("/notifications/{notification_id}/create-session", response_model=Session, status_code=201)
async def create_session_from_notification(
    notification_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """
    Create or retrieve a session from an email notification.
    If a session already exists for this email, return it. Otherwise, create a new one.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Creating session from notification {notification_id} for user {current_user.id}")
    
    from app.models.database import Notification as NotificationModel
    from app.services.email_action_processor import EmailActionProcessor
    from app.services.email_analyzer import EmailAnalyzer
    from app.services.email_service import EmailService
    from app.core.dependencies import get_ollama_client, get_memory_manager, get_daily_session_manager
    
    # Get notification
    notification_result = await db.execute(
        select(NotificationModel).where(
            NotificationModel.id == notification_id,
            NotificationModel.tenant_id == tenant_id,
        )
    )
    notification = notification_result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    # Only handle email_received notifications
    if notification.type != "email_received":
        raise HTTPException(status_code=400, detail="This endpoint only supports email_received notifications")
    
    content = notification.content or {}
    email_id = content.get("email_id")
    
    if not email_id:
        raise HTTPException(status_code=400, detail="Notification does not contain email_id")
    
    # Check if this email was already processed (check messages, not sessions)
    from app.models.database import Message as MessageModel
    existing_message_result = await db.execute(
        select(MessageModel).where(
            MessageModel.tenant_id == tenant_id,
            MessageModel.session_metadata["email_id"].astext == str(email_id),
        ).limit(1)
    )
    existing_message = existing_message_result.scalar_one_or_none()
    
    if existing_message:
        # Email already processed, return the session it's in
        existing_session_result = await db.execute(
            select(SessionModel).where(SessionModel.id == existing_message.session_id)
        )
        existing_session = existing_session_result.scalar_one_or_none()
        if existing_session:
            logger.info(f"Email {email_id} already processed in session {existing_session.id}, returning it")
            return Session(
                id=existing_session.id,
                name=existing_session.name,
                title=existing_session.title,
                description=existing_session.description,
                status=existing_session.status,
                created_at=existing_session.created_at,
                updated_at=existing_session.updated_at,
                archived_at=existing_session.archived_at,
                metadata=existing_session.session_metadata or {},
            )
    
    # Get email integration for current user
    from app.models.database import Integration
    from app.api.integrations.emails import _decrypt_credentials
    from sqlalchemy import or_
    
    integration_result = await db.execute(
        select(Integration).where(
            Integration.provider == "google",
            Integration.service_type == "email",
            Integration.enabled == True,
            Integration.tenant_id == tenant_id,
            or_(Integration.user_id == current_user.id, Integration.user_id.is_(None))
        ).order_by(Integration.user_id.desc())  # Prefer integrations with user_id
    )
    integration = integration_result.scalar_one_or_none()
    
    if not integration:
        raise HTTPException(status_code=404, detail="No email integration found for current user")
    
    # Fetch email details from Gmail
    try:
        credentials = _decrypt_credentials(
            integration.credentials_encrypted,
            settings.credentials_encryption_key
        )
        
        email_service = EmailService()
        await email_service.setup_gmail(credentials, str(integration.id))
        
        # Get email details
        messages = await email_service.get_gmail_messages(
            max_results=1,
            query=f"rfc822msgid:{email_id}",
            integration_id=str(integration.id),
            include_body=True,
        )
        
        if not messages:
            # Try searching by ID directly
            try:
                from googleapiclient.discovery import build
                from google.oauth2.credentials import Credentials
                creds = Credentials.from_authorized_user_info(credentials)
                service = build('gmail', 'v1', credentials=creds)
                msg_detail = service.users().messages().get(
                    userId="me",
                    id=email_id,
                    format="full"
                ).execute()
                
                # Extract email data
                headers = {h["name"]: h["value"] for h in msg_detail["payload"].get("headers", [])}
                email_data = {
                    "id": email_id,
                    "subject": headers.get("Subject", ""),
                    "from": headers.get("From", ""),
                    "to": headers.get("To", ""),
                    "date": headers.get("Date", ""),
                    "snippet": msg_detail.get("snippet", ""),
                    "body": email_service._extract_email_body(msg_detail["payload"]),
                }
            except Exception as e:
                logger.error(f"Error fetching email {email_id} from Gmail: {e}")
                # Use notification content as fallback
                email_data = {
                    "id": email_id,
                    "subject": content.get("subject", "No Subject"),
                    "from": content.get("from", "Unknown"),
                    "snippet": content.get("snippet", ""),
                    "body": content.get("snippet", ""),  # Use snippet as body fallback
                }
        else:
            email_data = messages[0]
        
    except Exception as e:
        logger.error(f"Error fetching email from Gmail: {e}", exc_info=True)
        # Use notification content as fallback
        email_data = {
            "id": email_id,
            "subject": content.get("subject", "No Subject"),
            "from": content.get("from", "Unknown"),
            "snippet": content.get("snippet", ""),
            "body": content.get("snippet", ""),
        }
    
    # Analyze email if analysis not already present
    analysis = content.get("analysis")
    if not analysis:
        try:
            ollama_client = get_ollama_client()
            email_analyzer = EmailAnalyzer(ollama_client=ollama_client)
            analysis = await email_analyzer.analyze_email(email_data)
        except Exception as e:
            logger.warning(f"Error analyzing email: {e}")
            # Use default analysis
            analysis = {
                "category": "direct",
                "requires_action": True,
                "action_type": "reply",
                "action_summary": "Email richiede attenzione",
                "urgency": "medium",
            }
    
    # Add email to today's daily session using EmailActionProcessor
    memory_manager = get_memory_manager()
    email_action_processor = EmailActionProcessor(
        db=db,
        memory_manager=memory_manager,
        ollama_client=get_ollama_client(),
    )
    
    session_id = await email_action_processor.process_email_action(
        email=email_data,
        analysis=analysis,
        tenant_id=tenant_id,
        user_id=current_user.id,
    )
    
    if not session_id:
        raise HTTPException(status_code=500, detail="Failed to add email to daily session")
    
    # Get the daily session
    session_result = await db.execute(
        select(SessionModel).where(SessionModel.id == session_id)
    )
    session = session_result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=500, detail="Session was created but could not be retrieved")
    
    # Update notification with session_id (daily session)
    notification.content = {**content, "auto_session_id": str(session_id)}
    notification.session_id = session_id
    await db.commit()
    
    logger.info(f"Added email to daily session {session_id} from notification {notification_id}")
    
    return Session(
        id=session.id,
        name=session.name,
        title=session.title,
        description=session.description,
        status=session.status,
        created_at=session.created_at,
        updated_at=session.updated_at,
        archived_at=session.archived_at,
        metadata=session.session_metadata or {},
    )


@router.post("/{session_id}/notifications/{notification_id}/resolve")
async def resolve_notification(
    session_id: UUID,
    notification_id: UUID,
    resolution_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    """Resolve a notification (e.g., contradiction resolution)"""
    resolution = resolution_data.get("resolution", "")
    
    # Get the task queue
    task_queue = get_task_queue()
    
    # Find the task associated with this notification
    # For now, we'll find tasks by type and session
    tasks = task_queue.list_tasks(session_id)
    contradiction_task = None
    for task in tasks:
        if task.type == "resolve_contradiction" and task.status in [TaskStatus.WAITING_USER, TaskStatus.IN_PROGRESS]:
            # Check if this task matches the notification
            task_payload = task.payload or {}
            task_notification_id = task_payload.get("notification_id")
            if str(task_notification_id) == str(notification_id):
                contradiction_task = task
                break
    
    if not contradiction_task:
        # Try to find any waiting contradiction task for this session
        for task in tasks:
            if task.type == "resolve_contradiction" and task.status == TaskStatus.WAITING_USER:
                contradiction_task = task
                break
    
    if contradiction_task:
        # Update task with resolution
        if resolution == "ignore":
            task_queue.complete_task(
                session_id,
                contradiction_task.id,
                payload_updates={
                    "user_response": resolution,
                    "resolution_type": "ignored",
                    "resolved_at": datetime.now(UTC).isoformat(),
                },
            )
        elif resolution == "no_contradiction":
            task_queue.complete_task(
                session_id,
                contradiction_task.id,
                payload_updates={
                    "user_response": resolution,
                    "resolution_type": "no_contradiction",
                    "resolved_at": datetime.now(UTC).isoformat(),
                },
            )
        else:
            # User provided a resolution
            task_queue.complete_task(
                session_id,
                contradiction_task.id,
                payload_updates={
                    "user_response": resolution,
                    "resolution_type": "resolved",
                    "resolved_at": datetime.now(UTC).isoformat(),
                },
            )
    
    # Mark notification as read
    service = NotificationService(db)
    await service.mark_as_read([notification_id])
    
    return {"status": "resolved", "notification_id": str(notification_id)}

