"""Authentication endpoints for user login, registration, and token management"""
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr, Field
import logging

from app.db.database import get_db
from app.models.database import User, Tenant
from app.core.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_email_verification_token,
    generate_password_reset_token,
)
from app.core.tenant_context import get_tenant_id
from app.core.user_context import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# Request/Response Models
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    name: Optional[str] = None
    tenant_id: Optional[UUID] = None  # Opzionale: se None, usa tenant dal contesto


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: dict


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None  # New refresh token (optional for backward compatibility)
    expires_in: int


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Register a new user"""
    # Use provided tenant_id or fallback to context tenant_id
    effective_tenant_id = request.tenant_id or tenant_id
    
    # Check if user already exists
    result = await db.execute(
        select(User).where(
            User.email == request.email,
            User.tenant_id == effective_tenant_id
        )
    )
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    # Verify tenant exists and is active
    tenant_result = await db.execute(
        select(Tenant).where(
            Tenant.id == effective_tenant_id,
            Tenant.active == True
        )
    )
    tenant = tenant_result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found or inactive"
        )
    
    # Hash password
    password_hash = hash_password(request.password)
    
    # Generate email verification token
    verification_token = generate_email_verification_token()
    
    # Create user
    user = User(
        tenant_id=effective_tenant_id,
        email=request.email,
        name=request.name,
        password_hash=password_hash,
        role="user",  # Default role
        email_verified=False,
        email_verification_token=verification_token,
        active=True,
    )
    
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    logger.info(f"User registered: {user.email} (tenant: {effective_tenant_id})")
    
    # Send verification email
    try:
        from app.services.email_sender import get_email_sender
        email_sender = get_email_sender()
        email_sent = await email_sender.send_invitation_email(
            to_email=user.email,
            user_name=user.name,
            verification_token=verification_token,
            admin_name=None,  # Self-registration, no admin
        )
        if email_sent:
            logger.info(f"Verification email sent to {user.email}")
        else:
            logger.warning(f"Failed to send verification email to {user.email} (check SMTP configuration)")
    except Exception as e:
        logger.error(f"Error sending verification email to {user.email}: {str(e)}", exc_info=True)
        # Don't fail registration if email fails - user can request resend
    
    return {
        "user_id": str(user.id),
        "email": user.email,
        "name": user.name,
        "email_verification_required": True,
    }


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    request_obj: Request,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Login user and return JWT tokens"""
    # Email matching should be case-insensitive
    from sqlalchemy import func
    normalized_email = request.email.lower().strip()
    logger.info(f"🔐 Login attempt for email: {request.email} (normalized: {normalized_email}), tenant_id: {tenant_id}")
    
    # Find user by email (case-insensitive) and tenant
    result = await db.execute(
        select(User).where(
            func.lower(User.email) == normalized_email,
            User.tenant_id == tenant_id,
            User.active == True
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        logger.warning(f"❌ Login failed: User not found for email {request.email} (normalized: {normalized_email}, tenant: {tenant_id})")
        # Don't reveal if user exists or not (security best practice)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Check if user has password (not API-only user)
    if not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Update last login
    user.last_login_at = datetime.now(timezone.utc)
    user.last_login_ip = request_obj.client.host if request_obj.client else None
    await db.commit()
    
    # Create tokens
    token_data = {
        "sub": str(user.id),  # Subject (user ID)
        "email": user.email,
        "tenant_id": str(user.tenant_id),
        "role": user.role,
    }
    
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    logger.info(f"User logged in: {user.email} (tenant: {tenant_id})")
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=15 * 60,  # 15 minutes in seconds
        user={
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "tenant_id": str(user.tenant_id),
            "role": user.role,
            "email_verified": user.email_verified,
        }
    )


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Refresh access token using refresh token"""
    # Decode refresh token
    payload = decode_token(request.refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    # Verify token type
    token_type = payload.get("type")
    if token_type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. Expected refresh token"
        )
    
    # Get user_id from token
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user ID"
        )
    
    try:
        user_uuid = UUID(str(user_id))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format"
        )
    
    # Verify user still exists and is active
    result = await db.execute(
        select(User).where(
            User.id == user_uuid,
            User.active == True
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Create new access token and refresh token (token rotation)
    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "tenant_id": str(user.tenant_id),
        "role": user.role,
    }
    
    access_token = create_access_token(token_data)
    # Generate new refresh token to implement token rotation (security best practice)
    new_refresh_token = create_refresh_token(token_data)
    
    logger.info(f"Token refreshed for user: {user.email} (tenant: {user.tenant_id})")
    
    return RefreshTokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,  # Return new refresh token for rotation
        expires_in=15 * 60,  # 15 minutes
    )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
):
    """Logout user (client should discard tokens)"""
    # In a more advanced implementation, we could:
    # - Store refresh tokens in database and revoke them
    # - Maintain a blacklist of tokens
    # For now, logout is handled client-side by discarding tokens
    
    logger.info(f"User logged out: {current_user.email}")
    
    return {"message": "Logged out successfully"}


@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """Get current authenticated user information"""
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "name": current_user.name,
        "tenant_id": str(current_user.tenant_id),
        "role": current_user.role,
        "email_verified": current_user.email_verified,
        "active": current_user.active,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "last_login_at": current_user.last_login_at.isoformat() if current_user.last_login_at else None,
    }


@router.get("/verify-email")
async def verify_email(
    token: str = Query(..., description="Email verification token"),
    db: AsyncSession = Depends(get_db),
):
    """Verify user email with verification token.

    If the user does not yet have a password (invited user), also generate
    a password reset token so the frontend can redirect directly to the
    password setup page.
    """
    logger.info(f"Email verification attempt with token: {token[:10]}...")
    
    # First, try to find user by token
    result = await db.execute(
        select(User).where(User.email_verification_token == token)
    )
    user = result.scalar_one_or_none()
    
    if user:
        # If already verified, just return info
        if user.email_verified:
            logger.info(f"Email already verified: {user.email}")
            return {
                "message": "Email already verified",
                "email": user.email,
                "already_verified": True,
                "password_reset_token": None,
            }
        
        # Verify email
        user.email_verified = True
        user.email_verification_token = None
        
        password_reset_token: Optional[str] = None
        # If user has no password yet (invitation flow), generate a reset token
        if not user.password_hash:
            password_reset_token = generate_password_reset_token()
            user.password_reset_token = password_reset_token
            # Set expiry (align with /password-reset/request: e.g. 1 hour)
            user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        
        await db.commit()
        await db.refresh(user)
        
        logger.info(f"Email verified: {user.email}")
        
        return {
            "message": "Email verified successfully",
            "email": user.email,
            "already_verified": False,
            "password_reset_token": password_reset_token,
        }
    
    # Token not found - likely already used or invalid
    logger.warning("Email verification failed: token not found")
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            "Invalid or expired verification token. "
            "The token may have already been used. "
            "If you already verified your email, you can proceed to login."
        ),
    )


@router.post("/password-reset/request")
async def request_password_reset(
    request: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Request password reset (sends email with reset token)"""
    result = await db.execute(
        select(User).where(
            User.email == request.email,
            User.tenant_id == tenant_id,
            User.active == True
        )
    )
    user = result.scalar_one_or_none()
    
    # Don't reveal if user exists (security)
    if not user:
        # Return success anyway to prevent email enumeration
        return {"message": "If the email exists, a password reset link has been sent"}
    
    # Generate reset token
    reset_token = generate_password_reset_token()
    user.password_reset_token = reset_token
    user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
    await db.commit()
    
    # TODO: Send email with reset link
    # For now, return token (remove in production)
    logger.info(f"Password reset requested for: {user.email}")
    
    return {
        "message": "If the email exists, a password reset link has been sent",
        "reset_token": reset_token,  # Remove in production
    }


@router.post("/password-reset/confirm")
async def confirm_password_reset(
    request: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
):
    """Confirm password reset with token"""
    # Accept tokens that are either not expired OR have no explicit expiry
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(User).where(
            User.password_reset_token == request.token,
            (User.password_reset_expires == None) | (User.password_reset_expires > now),
        )
    )  # type: ignore
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Update password
    user.password_hash = hash_password(request.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    await db.commit()
    
    logger.info(f"Password reset completed for: {user.email}")
    
    return {"message": "Password reset successfully"}


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change password for current user"""
    if not current_user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no password set"
        )
    
    # Verify current password
    if not verify_password(request.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Update password
    current_user.password_hash = hash_password(request.new_password)
    await db.commit()
    
    logger.info(f"Password changed for: {current_user.email}")
    
    return {"message": "Password changed successfully"}

