from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
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
):
    """Retrieve medium-term memory for a session"""
    results = await memory.retrieve_medium_term_memory(
        session_id, query, n_results
    )
    return {"session_id": session_id, "query": query, "results": results}


@router.get("/long")
async def get_long_term_memory(
    query: str,
    n_results: int = 5,
    min_importance: float = None,
    memory: MemoryManager = Depends(get_memory_manager),
):
    """Retrieve long-term memory"""
    results = await memory.retrieve_long_term_memory(
        query, n_results, min_importance
    )
    return {"query": query, "results": results}


@router.post("/long")
async def add_long_term_memory(
    memory_data: MemoryLongCreate,
    learned_from_sessions: List[UUID],
    db: AsyncSession = Depends(get_db),
    memory: MemoryManager = Depends(get_memory_manager),
):
    """Add content to long-term memory"""
    await memory.add_long_term_memory(
        db,
        memory_data.content,
        learned_from_sessions,
        memory_data.importance_score,
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

