"""User management endpoints (admin only)"""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel, EmailStr, Field
import logging

from app.db.database import get_db
from app.models.database import User
from app.core.tenant_context import get_tenant_id
from app.core.user_context import get_current_user, require_admin
from app.core.auth import hash_password, generate_email_verification_token
from app.services.email_sender import get_email_sender

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/users", tags=["users"])


# Request/Response Models
class UserCreate(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8, description="Password must be at least 8 characters")
    role: str = Field(default="user", pattern="^(admin|user|viewer)$")
    send_invitation_email: bool = False  # TODO: Implement email sending


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = Field(None, pattern="^(admin|user|viewer)$")
    active: Optional[bool] = None


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: Optional[str]
    role: str
    active: bool
    email_verified: bool
    last_login_at: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


@router.get("", response_model=List[UserResponse])
async def list_users(
    role: Optional[str] = Query(None, pattern="^(admin|user|viewer)$"),
    active: Optional[bool] = Query(None),
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """List all users for current tenant (admin only)"""
    query = select(User).where(User.tenant_id == tenant_id)
    
    if role:
        query = query.where(User.role == role)
    if active is not None:
        query = query.where(User.active == active)
    
    query = query.order_by(User.created_at.desc())
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return [
        UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            active=user.active,
            email_verified=user.email_verified,
            last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
            created_at=user.created_at.isoformat() if user.created_at else None,
        )
        for user in users
    ]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Create a new user (admin only)"""
    # Check if user already exists
    result = await db.execute(
        select(User).where(
            User.email == user_data.email,
            User.tenant_id == tenant_id
        )
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Hash password if provided
    password_hash = None
    if user_data.password:
        password_hash = hash_password(user_data.password)
    
    # Generate email verification token if sending invitation
    verification_token = None
    if user_data.send_invitation_email:
        verification_token = generate_email_verification_token()
    
    # Create user
    user = User(
        tenant_id=tenant_id,
        email=user_data.email,
        name=user_data.name,
        password_hash=password_hash,
        role=user_data.role,
        email_verified=False,
        email_verification_token=verification_token,
        active=True,
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    logger.info(f"User created by admin {current_user.email}: {user.email} (tenant: {tenant_id})")
    
    # Send invitation email if requested
    if user_data.send_invitation_email and verification_token:
        email_sender = get_email_sender()
        email_sent = await email_sender.send_invitation_email(
            to_email=user.email,
            user_name=user.name,
            verification_token=verification_token,
            admin_name=current_user.name or current_user.email,
        )
        if email_sent:
            logger.info(f"Invitation email sent to {user.email}")
        else:
            logger.warning(f"Failed to send invitation email to {user.email} (check SMTP configuration)")
    
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        active=user.active,
        email_verified=user.email_verified,
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Get user by ID (admin only)"""
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.tenant_id == tenant_id
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        active=user.active,
        email_verified=user.email_verified,
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_data: UserUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Update user (admin only)"""
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.tenant_id == tenant_id
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent admin from deactivating themselves
    if user_id == current_user.id and user_data.active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate yourself"
        )
    
    # Update fields
    update_data = user_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
    
    await db.commit()
    await db.refresh(user)
    
    logger.info(f"User updated by admin {current_user.email}: {user.email}")
    
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        active=user.active,
        email_verified=user.email_verified,
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Deactivate user (admin only) - soft delete"""
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.tenant_id == tenant_id
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent admin from deactivating themselves
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate yourself"
        )
    
    # Soft delete: set active to False
    user.active = False
    await db.commit()
    
    logger.info(f"User deactivated by admin {current_user.email}: {user.email}")
    
    return None

