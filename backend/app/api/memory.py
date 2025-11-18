from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from uuid import UUID
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.db.database import get_db
from app.models.schemas import MemoryMedium, MemoryLong, MemoryLongCreate
from app.core.dependencies import get_memory_manager
from app.core.memory_manager import MemoryManager
from app.services.advanced_search import AdvancedSearch
from app.services.memory_consolidator import MemoryConsolidator
from app.core.tenant_context import get_tenant_id
from app.core.user_context import get_current_user, require_admin
from app.models.database import User, MemoryLong as MemoryLongModel

router = APIRouter()


class HybridSearchRequest(BaseModel):
    query: str
    n_results: int = 5
    semantic_weight: float = 0.7
    keyword_weight: float = 0.3
    min_importance: Optional[float] = None
    content_type: Optional[str] = None


@router.get("/medium/{session_id}")
async def get_medium_term_memory(
    session_id: UUID,
    query: str,
    n_results: int = 5,
    memory: MemoryManager = Depends(get_memory_manager),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Retrieve medium-term memory for a session (for current tenant)"""
    # Verify session belongs to tenant
    from app.models.database import Session as SessionModel
    from sqlalchemy import select
    session_result = await db.execute(
        select(SessionModel).where(
            SessionModel.id == session_id,
            SessionModel.tenant_id == tenant_id
        )
    )
    if not session_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Session not found")
    results = await memory.retrieve_medium_term_memory(
        session_id, query, n_results, tenant_id=tenant_id
    )
    return {"session_id": session_id, "query": query, "results": results}


@router.get("/long")
async def get_long_term_memory(
    query: str,
    n_results: int = 5,
    min_importance: float = None,
    memory: MemoryManager = Depends(get_memory_manager),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Retrieve long-term memory (for current tenant)"""
    results = await memory.retrieve_long_term_memory(
        query, n_results, min_importance, tenant_id=tenant_id
    )
    return {"query": query, "results": results}


@router.post("/long")
async def add_long_term_memory(
    memory_data: MemoryLongCreate,
    learned_from_sessions: List[UUID],
    db: AsyncSession = Depends(get_db),
    memory: MemoryManager = Depends(get_memory_manager),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Add content to long-term memory (for current tenant)"""
    await memory.add_long_term_memory(
        db,
        memory_data.content,
        learned_from_sessions,
        memory_data.importance_score,
        tenant_id=tenant_id,
    )
    return {"message": "Memory added successfully"}


@router.post("/search/hybrid")
async def hybrid_search(
    request: HybridSearchRequest,
    memory: MemoryManager = Depends(get_memory_manager),
):
    """Perform hybrid search (semantic + keyword)"""
    search_service = AdvancedSearch(memory_manager=memory)
    results = await search_service.hybrid_search(
        query=request.query,
        n_results=request.n_results,
        semantic_weight=request.semantic_weight,
        keyword_weight=request.keyword_weight,
        min_importance=request.min_importance,
        content_type=request.content_type,
    )
    return {"query": request.query, "results": results}


@router.get("/search/suggest")
async def suggest_related(
    query: str,
    n_suggestions: int = Query(default=3, ge=1, le=10),
    memory: MemoryManager = Depends(get_memory_manager),
):
    """Suggest related queries based on search results"""
    search_service = AdvancedSearch(memory_manager=memory)
    suggestions = await search_service.suggest_related(query, n_suggestions)
    return {"query": query, "suggestions": suggestions}


@router.get("/search/cross-session")
async def cross_session_search(
    query: str,
    session_ids: Optional[List[UUID]] = Query(default=None),
    n_results: int = 5,
    memory: MemoryManager = Depends(get_memory_manager),
):
    """Search across multiple sessions"""
    search_service = AdvancedSearch(memory_manager=memory)
    results = await search_service.cross_session_search(
        query=query,
        session_ids=session_ids,
        n_results=n_results,
    )
    return {"query": query, "results": results}


@router.post("/consolidate/duplicates")
async def consolidate_duplicates(
    similarity_threshold: float = Query(default=0.85, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
    memory: MemoryManager = Depends(get_memory_manager),
):
    """Consolidate duplicate or similar memories"""
    consolidator = MemoryConsolidator(memory_manager=memory)
    stats = await consolidator.consolidate_duplicates(db, similarity_threshold)
    return {"message": "Consolidation completed", "stats": stats}


@router.post("/consolidate/summarize")
async def summarize_old_memories(
    days_old: int = Query(default=90, ge=1),
    max_memories: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    memory: MemoryManager = Depends(get_memory_manager),
):
    """Summarize old memories to reduce storage"""
    consolidator = MemoryConsolidator(memory_manager=memory)
    stats = await consolidator.summarize_old_memories(db, days_old, max_memories)
    return {"message": "Summarization completed", "stats": stats}


@router.get("/long/list")
async def list_long_term_memory(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    min_importance: Optional[float] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """List all long-term memory items (for current tenant)"""
    query = select(MemoryLongModel).where(
        MemoryLongModel.tenant_id == tenant_id
    )
    
    if min_importance is not None:
        query = query.where(MemoryLongModel.importance_score >= min_importance)
    
    query = query.order_by(MemoryLongModel.created_at.desc()).limit(limit).offset(offset)
    
    result = await db.execute(query)
    memories = result.scalars().all()
    
    total_result = await db.execute(
        select(MemoryLongModel).where(MemoryLongModel.tenant_id == tenant_id)
    )
    total = len(total_result.scalars().all())
    
    return {
        "items": [
            {
                "id": str(m.id),
                "content": m.content,
                "importance_score": m.importance_score,
                "learned_from_sessions": m.learned_from_sessions or [],
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "embedding_id": m.embedding_id,
            }
            for m in memories
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


class DeleteMemoryBatchRequest(BaseModel):
    memory_ids: List[UUID]


@router.post("/long/batch/delete")
async def delete_long_term_memory_batch(
    request: DeleteMemoryBatchRequest,
    db: AsyncSession = Depends(get_db),
    memory: MemoryManager = Depends(get_memory_manager),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(require_admin),
):
    """Delete multiple long-term memory items (admin only)"""
    if not request.memory_ids:
        raise HTTPException(status_code=400, detail="No memory IDs provided")
    
    memory_ids = request.memory_ids
    
    # Get memories to delete (only for current tenant)
    result = await db.execute(
        select(MemoryLongModel).where(
            MemoryLongModel.id.in_(memory_ids),
            MemoryLongModel.tenant_id == tenant_id,
        )
    )
    memories_to_delete = result.scalars().all()
    
    if not memories_to_delete:
        raise HTTPException(status_code=404, detail="No memories found to delete")
    
    # Delete from ChromaDB first
    deleted_from_chroma = 0
    for mem in memories_to_delete:
        if mem.embedding_id:
            try:
                collection = memory.long_term_memory_collection
                collection.delete(ids=[mem.embedding_id])
                deleted_from_chroma += 1
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to delete embedding {mem.embedding_id} from ChromaDB: {e}")
    
    # Delete from database
    for mem in memories_to_delete:
        await db.delete(mem)
    
    await db.commit()
    
    return {
        "message": f"Deleted {len(memories_to_delete)} memory items",
        "deleted_count": len(memories_to_delete),
        "deleted_from_chroma": deleted_from_chroma,
    }

