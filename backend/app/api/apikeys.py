"""API endpoints for managing API keys"""
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import secrets
import hashlib

from app.db.database import get_db
from app.core.tenant_context import get_tenant_id
from app.models.database import ApiKey, Tenant

router = APIRouter(prefix="/api/v1/apikeys", tags=["apikeys"])


class ApiKeyCreate(BaseModel):
    name: Optional[str] = None
    expires_in_days: Optional[int] = None  # Optional expiration in days


class ApiKeyResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: Optional[str]
    key: str  # Only returned on creation
    active: bool
    last_used_at: Optional[datetime]
    created_at: datetime
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True


class ApiKeyListResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: Optional[str]
    active: bool
    last_used_at: Optional[datetime]
    created_at: datetime
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True


@router.post("", response_model=ApiKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    api_key_data: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Create a new API key for the current tenant"""
    # Generate a secure random API key
    api_key = f"kn_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    # Calculate expiration if provided
    expires_at = None
    if api_key_data.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=api_key_data.expires_in_days)
    
    # Create API key record
    api_key_record = ApiKey(
        tenant_id=tenant_id,
        key_hash=key_hash,
        name=api_key_data.name,
        active=True,
        expires_at=expires_at,
    )
    db.add(api_key_record)
    await db.commit()
    await db.refresh(api_key_record)
    
    return ApiKeyResponse(
        id=api_key_record.id,
        tenant_id=api_key_record.tenant_id,
        name=api_key_record.name,
        key=api_key,  # Return the plain key only once
        active=api_key_record.active,
        last_used_at=api_key_record.last_used_at,
        created_at=api_key_record.created_at,
        expires_at=api_key_record.expires_at,
    )


@router.get("", response_model=List[ApiKeyListResponse])
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    active_only: bool = False,
):
    """List all API keys for the current tenant"""
    query = select(ApiKey).where(ApiKey.tenant_id == tenant_id)
    
    if active_only:
        query = query.where(ApiKey.active == True)
    
    result = await db.execute(query.order_by(ApiKey.created_at.desc()))
    api_keys = result.scalars().all()
    
    return [
        ApiKeyListResponse(
            id=key.id,
            tenant_id=key.tenant_id,
            name=key.name,
            active=key.active,
            last_used_at=key.last_used_at,
            created_at=key.created_at,
            expires_at=key.expires_at,
        )
        for key in api_keys
    ]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Revoke (deactivate) an API key"""
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.tenant_id == tenant_id
        )
    )
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    api_key.active = False
    await db.commit()
    
    return None

