"""Temporary initialization endpoint for creating admin user"""
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from typing import Optional
import logging

from app.db.database import get_db
from app.models.database import User, Tenant
from app.core.auth import hash_password
from app.core.tenant_context import get_tenant_id
from uuid import UUID

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/init", tags=["init"])


class CreateAdminRequest(BaseModel):
    email: EmailStr = "admin@example.com"
    password: str = "admin123"
    name: str = "Admin User"


@router.post("/admin")
async def create_admin_user(
    request: CreateAdminRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """
    Create admin user in the default tenant.
    This endpoint should be called once after initial deployment.
    """
    try:
        # Get default tenant
        result = await db.execute(
            select(Tenant).where(Tenant.schema_name == "tenant_default")
        )
        default_tenant = result.scalar_one_or_none()
        
        if not default_tenant:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Default tenant not found. Run migrations first."
            )
        
        # Check if user already exists
        result = await db.execute(
            select(User).where(
                User.email == request.email,
                User.tenant_id == default_tenant.id
            )
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            # Update password if user exists
            existing_user.password_hash = hash_password(request.password)
            existing_user.role = "admin"
            existing_user.email_verified = True
            existing_user.active = True
            await db.commit()
            await db.refresh(existing_user)
            
            logger.info(f"Updated admin user: {existing_user.email}")
            return {
                "message": "Admin user updated",
                "email": existing_user.email,
                "name": existing_user.name,
                "role": existing_user.role,
                "user_id": str(existing_user.id),
            }
        
        # Create admin user
        password_hash = hash_password(request.password)
        
        admin_user = User(
            tenant_id=default_tenant.id,
            email=request.email,
            name=request.name,
            password_hash=password_hash,
            role="admin",
            email_verified=True,
            active=True,
        )
        
        db.add(admin_user)
        await db.commit()
        await db.refresh(admin_user)
        
        logger.info(f"Admin user created: {admin_user.email}")
        
        return {
            "message": "Admin user created successfully",
            "email": admin_user.email,
            "name": admin_user.name,
            "role": admin_user.role,
            "user_id": str(admin_user.id),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating admin user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating admin user: {str(e)}"
        )

