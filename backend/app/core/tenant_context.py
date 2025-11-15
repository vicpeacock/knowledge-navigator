"""Tenant Context for Multi-Tenancy

This module provides tenant context extraction and dependency injection
for FastAPI endpoints. It supports:
- X-Tenant-ID header (direct tenant ID)
- X-API-Key header (API key lookup - TODO: Step 9)
- Default tenant (backward compatibility)
"""
from typing import Optional
from uuid import UUID
from fastapi import Header, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.db.database import get_db
from app.models.database import Tenant, ApiKey
import hashlib
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Cache for default tenant ID (set on startup)
DEFAULT_TENANT_ID: Optional[UUID] = None


async def get_tenant_id(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> UUID:
    """
    Extract tenant_id from request headers.
    
    Priority:
    1. X-Tenant-ID header (direct tenant ID)
    2. X-API-Key header (API key lookup - TODO: Step 9)
    3. Default tenant (backward compatibility)
    
    Args:
        x_tenant_id: Tenant ID from X-Tenant-ID header
        x_api_key: API key from X-API-Key header (not implemented yet)
        db: Database session
        
    Returns:
        UUID: Tenant ID
        
    Raises:
        HTTPException: If tenant not found or invalid
    """
    # Priority 1: X-Tenant-ID header
    if x_tenant_id:
        try:
            tenant_id = UUID(x_tenant_id)
            # Validate tenant exists and is active
            result = await db.execute(
                select(Tenant).where(
                    Tenant.id == tenant_id,
                    Tenant.active == True
                )
            )
            tenant = result.scalar_one_or_none()
            if not tenant:
                logger.warning(f"Tenant not found or inactive: {tenant_id}")
                raise HTTPException(status_code=404, detail="Tenant not found or inactive")
            logger.debug(f"Using tenant from X-Tenant-ID header: {tenant_id}")
            return tenant_id
        except ValueError:
            logger.warning(f"Invalid tenant ID format: {x_tenant_id}")
            raise HTTPException(status_code=400, detail="Invalid tenant ID format")
    
    # Priority 2: X-API-Key header (API Key authentication)
    if x_api_key:
        try:
            # Hash the API key (SHA-256 for fast lookups)
            key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
            
            # Lookup API key in database
            result = await db.execute(
                select(ApiKey).where(
                    ApiKey.key_hash == key_hash,
                    ApiKey.active == True
                )
            )
            api_key = result.scalar_one_or_none()
            
            if not api_key:
                logger.warning("Invalid or inactive API key")
                raise HTTPException(status_code=401, detail="Invalid or inactive API key")
            
            # Check expiration
            if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
                logger.warning(f"Expired API key: {api_key.id}")
                raise HTTPException(status_code=401, detail="API key has expired")
            
            # Update last_used_at
            api_key.last_used_at = datetime.now(timezone.utc)
            await db.commit()
            
            # Get tenant and verify it's active
            tenant_result = await db.execute(
                select(Tenant).where(
                    Tenant.id == api_key.tenant_id,
                    Tenant.active == True
                )
            )
            tenant = tenant_result.scalar_one_or_none()
            
            if not tenant:
                logger.warning(f"Tenant not found or inactive for API key: {api_key.tenant_id}")
                raise HTTPException(status_code=404, detail="Tenant not found or inactive")
            
            logger.debug(f"Using tenant from API key: {api_key.tenant_id}")
            return api_key.tenant_id
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error validating API key: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Error validating API key")
    
    # Priority 3: Default tenant (backward compatibility)
    global DEFAULT_TENANT_ID
    if DEFAULT_TENANT_ID:
        logger.debug(f"Using cached default tenant: {DEFAULT_TENANT_ID}")
        return DEFAULT_TENANT_ID
    
    # Fallback: get default tenant from database (first time only)
    logger.debug("Fetching default tenant from database")
    result = await db.execute(
        select(Tenant).where(Tenant.schema_name == "tenant_default")
    )
    default_tenant = result.scalar_one_or_none()
    if not default_tenant:
        logger.error("Default tenant not configured in database!")
        raise HTTPException(status_code=500, detail="Default tenant not configured")
    
    # Cache the default tenant ID for future requests
    DEFAULT_TENANT_ID = default_tenant.id
    logger.info(f"Cached default tenant ID: {DEFAULT_TENANT_ID}")
    
    return default_tenant.id


class TenantContext:
    """Context object for current tenant"""
    
    def __init__(self, tenant_id: UUID, schema_name: str, name: str):
        self.tenant_id = tenant_id
        self.schema_name = schema_name
        self.name = name
    
    def __repr__(self):
        return f"TenantContext(tenant_id={self.tenant_id}, schema_name={self.schema_name}, name={self.name})"


async def get_tenant_context(
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    """
    Get full tenant context including schema name.
    
    This dependency should be used in endpoints that need full tenant information.
    For endpoints that only need tenant_id, use get_tenant_id() directly.
    
    Args:
        tenant_id: Tenant ID from get_tenant_id dependency
        db: Database session
        
    Returns:
        TenantContext: Full tenant context
        
    Raises:
        HTTPException: If tenant not found
    """
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        logger.error(f"Tenant not found: {tenant_id}")
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    return TenantContext(
        tenant_id=tenant.id,
        schema_name=tenant.schema_name,
        name=tenant.name
    )


async def initialize_default_tenant(db: AsyncSession) -> Optional[UUID]:
    """
    Initialize and cache the default tenant ID.
    Should be called at application startup.
    
    Args:
        db: Database session
        
    Returns:
        Optional[UUID]: Default tenant ID, or None if not found
    """
    global DEFAULT_TENANT_ID
    
    if DEFAULT_TENANT_ID:
        logger.info(f"Default tenant already cached: {DEFAULT_TENANT_ID}")
        return DEFAULT_TENANT_ID
    
    result = await db.execute(
        select(Tenant).where(Tenant.schema_name == "tenant_default")
    )
    default_tenant = result.scalar_one_or_none()
    
    if default_tenant:
        DEFAULT_TENANT_ID = default_tenant.id
        logger.info(f"Initialized default tenant: {default_tenant.name} (ID: {DEFAULT_TENANT_ID})")
        return DEFAULT_TENANT_ID
    else:
        logger.error("Default tenant not found in database!")
        return None

