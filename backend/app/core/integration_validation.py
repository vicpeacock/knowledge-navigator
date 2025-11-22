"""Validation utilities for Integration model"""
from typing import Optional
from uuid import UUID
from fastapi import HTTPException
from app.models.database import User

def validate_integration_purpose(
    purpose: str,
    user_id: Optional[UUID],
    current_user: Optional[User] = None,
    is_admin_required: bool = False,
) -> None:
    """
    Validate that purpose and user_id are consistent.
    
    Rules:
    - purpose starting with "user_" requires user_id IS NOT NULL
    - purpose starting with "service_" requires user_id IS NULL
    - Only admin can create service_* integrations (if is_admin_required=True)
    
    Args:
        purpose: Integration purpose (e.g., "user_email", "service_email")
        user_id: User ID (can be None)
        current_user: Current user (for admin check)
        is_admin_required: Whether admin role is required for service integrations
        
    Raises:
        HTTPException: If validation fails
    """
    if purpose.startswith("user_"):
        if user_id is None:
            raise HTTPException(
                status_code=400,
                detail=f"Integration with purpose '{purpose}' requires a user_id. user_* integrations must be associated with a user."
            )
    elif purpose.startswith("service_"):
        if user_id is not None:
            raise HTTPException(
                status_code=400,
                detail=f"Integration with purpose '{purpose}' must have user_id=NULL. service_* integrations are tenant-level."
            )
        if is_admin_required and current_user and current_user.role != "admin":
            raise HTTPException(
                status_code=403,
                detail="Only administrators can create service integrations."
            )
    # mcp_server purpose is allowed with or without user_id (tenant-level by default)

