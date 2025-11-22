"""User management endpoints (admin only)"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm.attributes import flag_modified
from pydantic import BaseModel, EmailStr, Field
import logging

from app.db.database import get_db
from app.models.database import User, Integration
from app.core.tenant_context import get_tenant_id
from app.core.user_context import get_current_user, require_admin
from app.core.auth import hash_password, generate_email_verification_token
from app.services.email_sender import get_email_sender
from app.core.oauth_utils import is_google_workspace_server

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
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    role: Optional[str] = Field(None, pattern="^(admin|user|viewer)$")
    active: Optional[bool] = None


class UserProfileUpdate(BaseModel):
    """Update model for current user's own profile"""
    name: Optional[str] = None
    timezone: Optional[str] = None


class BackgroundServicesPreferences(BaseModel):
    """Preferences for background services (email polling, calendar watching)"""
    email_notifications_enabled: Optional[bool] = True
    calendar_notifications_enabled: Optional[bool] = True


class BackgroundServicesPreferencesResponse(BaseModel):
    """Response model for background services preferences"""
    email_notifications_enabled: bool
    calendar_notifications_enabled: bool


class OAuthIntegrationStatus(BaseModel):
    """Status of OAuth authorization for an MCP integration"""
    integration_id: UUID
    integration_name: str
    server_url: str
    oauth_required: bool
    oauth_authorized: bool  # True if user has authorized OAuth for this integration
    google_email: Optional[str] = None  # Email of the authorized Google account


class OAuthIntegrationsResponse(BaseModel):
    """Response model for OAuth integrations status"""
    integrations: List[OAuthIntegrationStatus]


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: Optional[str]
    role: str
    active: bool
    email_verified: bool
    timezone: Optional[str] = None
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


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's profile"""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        role=current_user.role,
        active=current_user.active,
        email_verified=current_user.email_verified,
        timezone=current_user.timezone,
        last_login_at=current_user.last_login_at.isoformat() if current_user.last_login_at else None,
        created_at=current_user.created_at.isoformat() if current_user.created_at else None,
    )


@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    profile_data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user's own profile (name, timezone)"""
    update_data = profile_data.model_dump(exclude_unset=True)
    
    # Update allowed fields only
    if "name" in update_data:
        current_user.name = update_data["name"]
    if "timezone" in update_data:
        current_user.timezone = update_data["timezone"]
    
    await db.commit()
    await db.refresh(current_user)
    
    logger.info(f"User {current_user.email} updated their profile")
    
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        role=current_user.role,
        active=current_user.active,
        email_verified=current_user.email_verified,
        timezone=current_user.timezone,
        last_login_at=current_user.last_login_at.isoformat() if current_user.last_login_at else None,
        created_at=current_user.created_at.isoformat() if current_user.created_at else None,
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
    
    # If email is being updated, ensure uniqueness per tenant
    update_data = user_data.model_dump(exclude_unset=True)
    new_email = update_data.get("email")
    if new_email and new_email != user.email:
        # Check if another user with same email exists in this tenant
        result = await db.execute(
            select(User).where(
                User.tenant_id == tenant_id,
                User.email == new_email,
                User.id != user_id,
            )
        )
        conflict = result.scalar_one_or_none()
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Another user with this email already exists",
            )

    # Update fields
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


@router.post("/{user_id}/resend-invitation", status_code=status.HTTP_200_OK)
async def resend_invitation_email(
    user_id: UUID,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Resend verification/invitation email to an existing user (admin only)."""
    # Load user for this tenant
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.tenant_id == tenant_id,
        )
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send invitation to inactive user",
        )
    
    if user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User email is already verified",
        )
    
    # Generate a new verification token
    verification_token = generate_email_verification_token()
    user.email_verification_token = verification_token
    # Ensure email_verified is False until they confirm
    user.email_verified = False
    
    await db.commit()
    await db.refresh(user)
    
    # Send invitation/verification email
    email_sender = get_email_sender()
    email_sent = await email_sender.send_invitation_email(
        to_email=user.email,
        user_name=user.name,
        verification_token=verification_token,
        admin_name=current_user.name or current_user.email,
    )
    
    if email_sent:
        logger.info(f"Resent invitation email to {user.email}")
        return {"message": "Invitation email resent successfully"}
    
    logger.warning(f"Failed to resend invitation email to {user.email} (check SMTP configuration)")
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to send invitation email",
    )


class ToolPreference(BaseModel):
    """Tool preference for a user"""
    tool_name: str
    enabled: bool


class ToolsPreferencesResponse(BaseModel):
    """Response with available tools and user preferences"""
    available_tools: List[Dict[str, Any]]
    user_preferences: List[str]  # List of enabled tool names


class ToolsPreferencesUpdate(BaseModel):
    """Update user tool preferences"""
    enabled_tools: List[str]  # List of tool names to enable


@router.get("/me/tools", response_model=ToolsPreferencesResponse)
async def get_user_tools_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Get available tools and user's tool preferences"""
    import asyncio
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"🔧 Getting tools preferences for user {current_user.email}")
    
    from app.core.tool_manager import ToolManager
    
    # Get base tools (fast, synchronous)
    tool_manager = ToolManager(db=db, tenant_id=tenant_id)
    base_tools = tool_manager.get_base_tools()
    logger.info(f"   Found {len(base_tools)} base tools")
    
    # Get MCP tools with timeout (may be slow or unavailable)
    mcp_tools = []
    try:
        logger.info("   Fetching MCP tools with 10 second timeout...")
        mcp_tools = await asyncio.wait_for(
            tool_manager.get_mcp_tools(current_user=current_user, include_all=True),
            timeout=10.0  # 10 second timeout
        )
        logger.info(f"   Found {len(mcp_tools)} MCP tools")
    except asyncio.TimeoutError:
        logger.warning("   Timeout fetching MCP tools (MCP servers may be slow or unavailable)")
        mcp_tools = []
    except Exception as e:
        logger.warning(f"   Error loading MCP tools: {e}")
        mcp_tools = []
    
    available_tools = base_tools + mcp_tools
    logger.info(f"✅ Total available tools: {len(available_tools)}")
    
    # Get user's current preferences
    user_metadata = current_user.user_metadata or {}
    # Check if preferences key exists (distinguish between None/not set vs empty list)
    enabled_tools = user_metadata.get("enabled_tools")
    
    # If preferences key doesn't exist (None), return all tools as enabled (first time)
    # If preferences key exists but is empty list, return empty list (user explicitly deselected all)
    if enabled_tools is None:
        enabled_tools = [tool.get("name") for tool in available_tools if tool.get("name")]
    elif not isinstance(enabled_tools, list):
        # If it's not a list, treat as not set
        enabled_tools = [tool.get("name") for tool in available_tools if tool.get("name")]
    # else: enabled_tools is already a list (empty or with values), use it as-is
    
    return ToolsPreferencesResponse(
        available_tools=available_tools,
        user_preferences=enabled_tools,
    )


@router.put("/me/tools", response_model=ToolsPreferencesResponse)
async def update_user_tools_preferences(
    preferences: ToolsPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Update user's tool preferences"""
    from app.core.tool_manager import ToolManager
    
    # Get all available tools (not filtered by user preferences) for validation
    tool_manager = ToolManager(db=db, tenant_id=tenant_id)
    base_tools = tool_manager.get_base_tools()
    mcp_tools = await tool_manager.get_mcp_tools(current_user=current_user, include_all=True)
    all_available_tools = base_tools + mcp_tools
    available_tool_names = {tool.get("name") for tool in all_available_tools if tool.get("name")}
    
    # Validate requested tools
    invalid_tools = set(preferences.enabled_tools) - available_tool_names
    if invalid_tools:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tool names: {', '.join(invalid_tools)}"
        )
    
    # Update user metadata - use explicit UPDATE to ensure JSONB is saved correctly
    user_metadata = current_user.user_metadata or {}
    user_metadata = dict(user_metadata)  # Create a copy to ensure SQLAlchemy detects the change
    user_metadata["enabled_tools"] = preferences.enabled_tools
    
    # Use explicit UPDATE statement to ensure JSONB is saved correctly
    from sqlalchemy import update
    from app.models.database import User
    await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(user_metadata=user_metadata)
    )
    await db.commit()
    await db.refresh(current_user)
    
    logger.info(f"Updated tool preferences for user {current_user.email}: {len(preferences.enabled_tools)} tools enabled")
    
    # Return all available tools (not filtered) with user's preferences
    return ToolsPreferencesResponse(
        available_tools=all_available_tools,
        user_preferences=preferences.enabled_tools,
    )


@router.get("/me/background-services", response_model=BackgroundServicesPreferencesResponse)
async def get_background_services_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's background services preferences"""
    user_metadata = current_user.user_metadata or {}
    background_prefs = user_metadata.get("background_services", {})
    
    # Default values: both enabled by default
    email_enabled = background_prefs.get("email_notifications_enabled", True)
    calendar_enabled = background_prefs.get("calendar_notifications_enabled", True)
    
    return BackgroundServicesPreferencesResponse(
        email_notifications_enabled=email_enabled,
        calendar_notifications_enabled=calendar_enabled,
    )


@router.put("/me/background-services", response_model=BackgroundServicesPreferencesResponse)
async def update_background_services_preferences(
    preferences: BackgroundServicesPreferences,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user's background services preferences"""
    user_metadata = current_user.user_metadata or {}
    user_metadata = dict(user_metadata)  # Create a copy to ensure SQLAlchemy detects the change
    
    # Initialize background_services if not present
    if "background_services" not in user_metadata:
        user_metadata["background_services"] = {}
    
    # Create a new dict for background_services to ensure SQLAlchemy detects the change
    background_services = dict(user_metadata.get("background_services", {}))
    
    # Update preferences (only if provided)
    if preferences.email_notifications_enabled is not None:
        background_services["email_notifications_enabled"] = preferences.email_notifications_enabled
    if preferences.calendar_notifications_enabled is not None:
        background_services["calendar_notifications_enabled"] = preferences.calendar_notifications_enabled
    
    user_metadata["background_services"] = background_services
    
    # Use explicit UPDATE statement to ensure JSONB is saved correctly
    from sqlalchemy import update
    from app.models.database import User
    await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(user_metadata=user_metadata)
    )
    await db.commit()
    await db.refresh(current_user)
    
    logger.info(
        f"Updated background services preferences for user {current_user.email}: "
        f"email={background_services.get('email_notifications_enabled', True)}, "
        f"calendar={background_services.get('calendar_notifications_enabled', True)}"
    )
    
    return BackgroundServicesPreferencesResponse(
        email_notifications_enabled=background_services.get("email_notifications_enabled", True),
        calendar_notifications_enabled=background_services.get("calendar_notifications_enabled", True),
    )


@router.get("/me/oauth-integrations", response_model=OAuthIntegrationsResponse)
async def get_oauth_integrations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """
    Get list of MCP integrations that require OAuth and their authorization status for the current user.
    This endpoint is used by the Profile page to show which integrations need OAuth authorization.
    """
    logger.info(f"🔍 Getting OAuth integrations for user {current_user.email} (tenant: {tenant_id})")
    
    # Get all enabled MCP integrations for this tenant
    result = await db.execute(
        select(Integration).where(
            Integration.tenant_id == tenant_id,
            Integration.service_type == "mcp_server",
            Integration.enabled == True
        )
    )
    all_integrations = result.scalars().all()
    
    logger.info(f"   Found {len(all_integrations)} enabled MCP integrations")
    
    oauth_integrations = []
    user_id_str = str(current_user.id)
    
    for integration in all_integrations:
        session_metadata = integration.session_metadata or {}
        server_url = session_metadata.get("server_url", "") or ""
        integration_name = session_metadata.get("name", "") or server_url
        
        logger.info(f"   Checking integration {integration.id}: {integration_name}")
        logger.info(f"      Server URL: {server_url}")
        
        # Check if this is a Google Workspace MCP server (requires OAuth)
        is_google = is_google_workspace_server(server_url)
        oauth_required = session_metadata.get("oauth_required", False)
        
        logger.info(f"      Is Google Workspace server: {is_google}")
        logger.info(f"      OAuth required flag: {oauth_required}")
        
        # Also check oauth_required flag in metadata (some servers might have this set)
        if is_google or oauth_required:
            # Check if user has OAuth credentials for this integration
            oauth_credentials = session_metadata.get("oauth_credentials", {})
            oauth_authorized = user_id_str in oauth_credentials
            
            # Get Google email from stored metadata (saved during OAuth callback)
            google_email = None
            if oauth_authorized:
                # Try to get email from stored metadata first (more reliable)
                oauth_user_emails = session_metadata.get("oauth_user_emails", {})
                google_email = oauth_user_emails.get(user_id_str)
                
                if google_email:
                    logger.info(f"      📧 Retrieved Google email from stored metadata: {google_email}")
                else:
                    # Fallback: try to get email from API (if token is still valid)
                    logger.debug(f"      No stored email, attempting to retrieve from API...")
                    try:
                        from app.services.oauth_token_manager import OAuthTokenManager
                        from app.core.exceptions import OAuthAuthenticationRequiredError, OAuthTokenExpiredError
                        
                        try:
                            valid_token = await OAuthTokenManager.get_valid_token(
                                integration=integration,
                                user=current_user,
                                db=db,
                                auto_refresh=True
                            )
                            
                            if valid_token:
                                # Call Google API to get user info
                                import httpx
                                async with httpx.AsyncClient() as client:
                                    response = await client.get(
                                        "https://www.googleapis.com/oauth2/v2/userinfo",
                                        headers={"Authorization": f"Bearer {valid_token}"},
                                        timeout=5.0
                                    )
                                    if response.status_code == 200:
                                        user_info = response.json()
                                        google_email = user_info.get("email")
                                        logger.info(f"      📧 Retrieved Google email from API: {google_email}")
                                        
                                        # Save it for next time
                                        if "oauth_user_emails" not in session_metadata:
                                            session_metadata["oauth_user_emails"] = {}
                                        session_metadata["oauth_user_emails"][user_id_str] = google_email
                                        integration.session_metadata = session_metadata
                                        flag_modified(integration, "session_metadata")
                                        await db.commit()
                                    else:
                                        logger.debug(f"      ⚠️  Failed to get Google user info: {response.status_code}")
                        except (OAuthAuthenticationRequiredError, OAuthTokenExpiredError) as oauth_err:
                            logger.debug(f"      ⚠️  Could not retrieve email from API: {oauth_err}")
                    except Exception as email_error:
                        logger.debug(f"      ⚠️  Could not retrieve Google email: {email_error}")
            
            logger.info(f"      ✅ Adding to OAuth integrations list (authorized: {oauth_authorized}, email: {google_email})")
            logger.info(f"      📋 Session metadata keys: {list(session_metadata.keys())}")
            if "oauth_user_emails" in session_metadata:
                logger.info(f"      📋 OAuth user emails: {session_metadata.get('oauth_user_emails', {})}")
            
            oauth_integrations.append(
                OAuthIntegrationStatus(
                    integration_id=integration.id,
                    integration_name=integration_name,
                    server_url=server_url,
                    oauth_required=True,
                    oauth_authorized=oauth_authorized,
                    google_email=google_email,
                )
            )
        else:
            logger.info(f"      ⏭️  Skipping (not a Google Workspace server)")
    
    logger.info(f"✅ Returning {len(oauth_integrations)} OAuth integrations")
    return OAuthIntegrationsResponse(integrations=oauth_integrations)

