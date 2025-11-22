"""User Context for Authentication

This module provides user authentication and authorization dependencies
for FastAPI endpoints. It extracts user information from JWT tokens.
"""
from typing import Optional
from uuid import UUID
from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.db.database import get_db
from app.models.database import User
from app.core.auth import decode_token
from app.core.tenant_context import get_tenant_id

logger = logging.getLogger(__name__)


async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
) -> User:
    """
    Extract current user from JWT token in Authorization header.
    
    Args:
        authorization: Authorization header (Bearer <token>)
        db: Database session
        tenant_id: Tenant ID from tenant context
        
    Returns:
        User: Current authenticated user
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    logger.debug(f"[get_current_user] Called with tenant_id={tenant_id}, has_auth={bool(authorization)}")
    
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract token from "Bearer <token>"
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise ValueError("Invalid authorization scheme")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Decode JWT token
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract user_id from token
    user_id = payload.get("sub")  # Standard JWT claim for subject (user ID)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user ID",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        user_uuid = UUID(str(user_id))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format in token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify token type is access token
    token_type = payload.get("type")
    if token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. Expected access token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from database
    logger.debug(f"[get_current_user] Querying database for user_id={user_uuid}, tenant_id={tenant_id}")
    try:
        result = await db.execute(
            select(User).where(
                User.id == user_uuid,
                User.tenant_id == tenant_id,  # Ensure user belongs to current tenant
                User.active == True
            )
        )
        user = result.scalar_one_or_none()
        logger.debug(f"[get_current_user] Query completed, user found: {user is not None}")
    except Exception as db_error:
        logger.error(f"[get_current_user] Database query failed: {db_error}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error during authentication",
        ) from db_error
    
    if not user:
        logger.warning(f"User not found or inactive: {user_uuid} (tenant: {tenant_id})")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.debug(f"[get_current_user] Returning user: {user.email}")
    return user


async def require_role(
    required_role: str,
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Dependency to require a specific role.
    
    Args:
        required_role: Required role (admin, user, viewer)
        current_user: Current authenticated user
        
    Returns:
        User: Current user if role matches
        
    Raises:
        HTTPException: If user doesn't have required role
    """
    if current_user.role != required_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Required role: {required_role}. Current role: {current_user.role}",
        )
    
    return current_user


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Dependency to require admin role"""
    return await require_role("admin", current_user)

