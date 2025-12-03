"""Database Session with Tenant Context for RLS

This module provides a database session dependency that automatically
sets the tenant_id in the PostgreSQL session for Row Level Security (RLS).
"""
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.db.database import get_db
from app.core.tenant_context import get_tenant_id


async def get_db_with_tenant(
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> AsyncSession:
    """
    Get database session with tenant_id set for RLS.
    
    This dependency should be used instead of get_db() when RLS is enabled.
    It automatically sets app.current_tenant_id in the PostgreSQL session
    so that RLS policies can filter data by tenant.
    
    Args:
        tenant_id: Tenant ID from get_tenant_id dependency
        db: Database session from get_db dependency
        
    Yields:
        AsyncSession: Database session with tenant_id set for RLS
        
    Note:
        This function sets the tenant_id on the existing session.
        The session must not have been used yet for queries.
    """
    # Set tenant_id in PostgreSQL session for RLS
    from sqlalchemy import text
    await db.execute(text(f"SET app.current_tenant_id = '{tenant_id}'"))
    
    try:
        yield db
    finally:
        # Reset tenant_id when done
        await db.execute(text("RESET app.current_tenant_id"))
