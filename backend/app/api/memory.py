from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from app.db.database import get_db
from app.models.schemas import MemoryMedium, MemoryLong, MemoryLongCreate
from app.core.dependencies import get_memory_manager
from app.core.memory_manager import MemoryManager

router = APIRouter()


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

