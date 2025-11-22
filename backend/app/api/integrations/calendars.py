from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.models.database import Integration
from app.services.calendar_service import CalendarService
from app.services.exceptions import IntegrationAuthError
from app.services.date_parser import DateParser
from app.core.tenant_context import get_tenant_id
from app.core.user_context import get_current_user, require_admin
from app.core.integration_validation import validate_integration_purpose
from app.models.database import User  # type: ignore  # for type hints only
from cryptography.fernet import Fernet
import base64
import json

router = APIRouter()

# Global calendar service instance
_calendar_service = CalendarService()
_date_parser = DateParser()


def get_calendar_service() -> CalendarService:
    """Dependency to get calendar service"""
    return _calendar_service


def _encrypt_credentials(credentials: Dict[str, Any], key: str) -> str:
    """Encrypt credentials for storage"""
    try:
        # Ensure key is 32 bytes for Fernet
        key_bytes = key.encode()[:32].ljust(32, b'0')
        key_b64 = base64.urlsafe_b64encode(key_bytes)
        f = Fernet(key_b64)
        
        credentials_json = json.dumps(credentials)
        encrypted = f.encrypt(credentials_json.encode())
        return encrypted.decode()
    except Exception as e:
        raise ValueError(f"Error encrypting credentials: {str(e)}")


def _decrypt_credentials(encrypted: str, key: str) -> Dict[str, Any]:
    """Decrypt credentials from storage"""
    try:
        key_bytes = key.encode()[:32].ljust(32, b'0')
        key_b64 = base64.urlsafe_b64encode(key_bytes)
        f = Fernet(key_b64)
        
        decrypted = f.decrypt(encrypted.encode())
        return json.loads(decrypted.decode())
    except Exception as e:
        raise ValueError(f"Error decrypting credentials: {str(e)}")


class CalendarSetupRequest(BaseModel):
    provider: str  # google, apple, microsoft
    credentials: Optional[Dict[str, Any]] = None


class CalendarQueryRequest(BaseModel):
    query: str  # Natural language query like "eventi domani", "meeting questa settimana"
    provider: Optional[str] = "google"  # Which calendar provider to query
    integration_id: Optional[UUID] = None


@router.get("/oauth/authorize")
async def authorize_google_calendar(
    integration_id: Optional[UUID] = None,
    calendar_service: CalendarService = Depends(get_calendar_service),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """Start OAuth2 flow for Google Calendar"""
    from app.core.config import settings
    
    if not settings.google_client_id:
        raise HTTPException(
            status_code=400,
            detail="Google OAuth credentials not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env"
        )
    
    try:
        # Encode state with integration_id and user_id so callback can associate integration to user
        state_payload = {
            "integration_id": str(integration_id) if integration_id else None,
            "user_id": str(current_user.id),
        }
        import json as json_lib
        import base64

        state_str = base64.urlsafe_b64encode(
            json_lib.dumps(state_payload).encode("utf-8")
        ).decode("utf-8")

        flow = calendar_service.create_google_oauth_flow()
        # Pass state directly to authorization_url() to ensure it's preserved
        authorization_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
            state=state_str,  # Pass state directly to authorization_url
        )
        return {"authorization_url": authorization_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating OAuth flow: {str(e)}")


@router.get("/oauth/callback")
async def oauth_callback(
    code: str,
    tenant_id: UUID = Depends(get_tenant_id),
    state: Optional[str] = None,
    calendar_service: CalendarService = Depends(get_calendar_service),
    db: AsyncSession = Depends(get_db),
):
    """OAuth2 callback for Google Calendar"""
    from app.core.config import settings
    
    try:
        flow = calendar_service.create_google_oauth_flow()
        try:
            flow.fetch_token(code=code)
        except (Warning, ValueError) as exc:
            message = str(exc)
            if "Scope has changed" in message:
                # Extract new scope list from error message
                try:
                    new_scopes_part = message.split('to "')[1].split('"')[0]
                    new_scopes = [scope for scope in new_scopes_part.split() if scope]
                except Exception:  # pragma: no cover - fallback path
                    new_scopes = []
                if new_scopes:
                    flow = calendar_service.create_google_oauth_flow(scopes=new_scopes)
                    # Ensure oauthlib compares against updated scopes order
                    flow.oauth2session.scope = new_scopes
                    flow.fetch_token(code=code)
                else:
                    raise
            else:
                raise
        
        credentials = {
            "token": flow.credentials.token,
            "refresh_token": flow.credentials.refresh_token,
            "token_uri": flow.credentials.token_uri,
            "client_id": flow.credentials.client_id,
            "client_secret": flow.credentials.client_secret,
            "scopes": flow.credentials.scopes,
        }
        
        prior_refresh_token: Optional[str] = None
        
        # Decode state (may be raw UUID from older flow or base64-encoded JSON)
        integration_id: Optional[UUID] = None
        user_id: Optional[UUID] = None
        if state:
            import base64
            import json as json_lib
            import logging
            logger = logging.getLogger(__name__)

            try:
                # Try to decode as base64 JSON first
                # Fix padding if needed
                state_bytes = state.encode("utf-8")
                missing_padding = len(state_bytes) % 4
                if missing_padding:
                    state_bytes += b'=' * (4 - missing_padding)
                
                decoded = base64.urlsafe_b64decode(state_bytes)
                payload = json_lib.loads(decoded.decode("utf-8"))
                integration_id_str = payload.get("integration_id")
                user_id_str = payload.get("user_id")
                service_integration = payload.get("service_integration", False)
                
                logger.info(f"OAuth callback (Calendar) - Decoded state: integration_id={integration_id_str}, user_id={user_id_str}, service_integration={service_integration}")
                
                if integration_id_str:
                    integration_id = UUID(integration_id_str)
                if user_id_str:
                    user_id = UUID(user_id_str)
                    logger.info(f"OAuth callback (Calendar) - Setting user_id={user_id} for new integration")
                elif service_integration:
                    # Service integrations have user_id = NULL
                    user_id = None
                    logger.info(f"OAuth callback (Calendar) - Service integration, user_id=NULL")
            except Exception as e:
                logger.warning(f"OAuth callback - Failed to decode state as JSON: {e}, trying as UUID")
                # Fallback: treat state as raw UUID (old behavior)
                try:
                    integration_id = UUID(state)
                except (ValueError, TypeError):
                    integration_id = None
                    logger.warning(f"OAuth callback - State is not a valid UUID either: {state}")
        
        if integration_id:
            # Update existing integration (must belong to tenant)
            result = await db.execute(
                select(Integration).where(
                    Integration.id == integration_id,
                    Integration.tenant_id == tenant_id
                )
            )
            integration = result.scalar_one_or_none()
            if integration:
                try:
                    existing = _decrypt_credentials(
                        integration.credentials_encrypted,
                        settings.credentials_encryption_key,
                    )
                    prior_refresh_token = existing.get("refresh_token")
                except Exception:
                    prior_refresh_token = None

                if not credentials.get("refresh_token") and prior_refresh_token:
                    credentials["refresh_token"] = prior_refresh_token

                encrypted = _encrypt_credentials(credentials, settings.credentials_encryption_key)
                integration.credentials_encrypted = encrypted
                
                # IMPORTANTE: Aggiorna anche user_id e purpose se mancante o se fornito nello state
                if user_id and (not integration.user_id or integration.user_id != user_id):
                    logger.info(f"OAuth callback (Calendar) - Updating user_id for integration {integration_id}: {integration.user_id} -> {user_id}")
                    integration.user_id = user_id
                    # Ensure purpose is set correctly for user integration
                    if not integration.purpose or not integration.purpose.startswith("user_"):
                        integration.purpose = "user_calendar"
                        logger.info(f"OAuth callback (Calendar) - Updated purpose to user_calendar for integration {integration_id}")
                
                await db.commit()
            else:
                raise HTTPException(status_code=404, detail="Integration not found")
        else:
            # Create new integration (per-user if user_id provided)
            if not credentials.get("refresh_token"):
                raise HTTPException(
                    status_code=400,
                    detail="L'autorizzazione non ha fornito il refresh token. Concedi tutti i permessi richiesti e riprova."
                )
            encrypted = _encrypt_credentials(credentials, settings.credentials_encryption_key)
            # Determine purpose based on service_integration flag
            purpose = "service_calendar" if service_integration else "user_calendar"
            # Validate purpose and user_id consistency
            validate_integration_purpose(purpose, user_id)
            integration = Integration(
                provider="google",
                service_type="calendar",
                purpose=purpose,
                credentials_encrypted=encrypted,
                enabled=True,
                tenant_id=tenant_id,
                user_id=user_id,  # NULL for service integrations, user_id for user integrations
            )
            db.add(integration)
            await db.commit()
            await db.refresh(integration)
            integration_id = integration.id
        
        # Setup calendar service
        try:
            await calendar_service.setup_google(credentials, str(integration_id))
        except IntegrationAuthError as exc:
            raise HTTPException(
                status_code=401,
                detail={
                    "message": "Autorizzazione Google Calendar non valida.",
                    "reason": exc.reason,
                },
            )
        
        # Redirect to frontend with success
        # Determine redirect URL based on purpose
        frontend_url = "http://localhost:3003"  # Can be made configurable
        # Get the integration to check its purpose
        integration = await db.get(Integration, integration_id)
        if integration and integration.purpose in ("user_email", "user_calendar"):
            # User integrations redirect to profile page
            redirect_url = f"{frontend_url}/settings/profile?success=true&integration_id={integration_id}"
        else:
            # Service integrations redirect to integrations page (admin)
            redirect_url = f"{frontend_url}/integrations?success=true&integration_id={integration_id}"
        return RedirectResponse(url=redirect_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in OAuth callback: {str(e)}")


@router.post("/setup")
async def setup_calendar(
    request: CalendarSetupRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Setup calendar integration (for non-OAuth providers) - for current tenant"""
    if request.provider == "google":
        # For Google, use OAuth flow instead
        raise HTTPException(
            status_code=400,
            detail="Use /oauth/authorize endpoint for Google Calendar setup"
        )
    
    # For other providers, store credentials directly
    # Default to user_calendar if no purpose specified (for backward compatibility)
    integration = Integration(
        provider=request.provider,
        service_type="calendar",
        purpose="user_calendar",  # Default to user_calendar for non-OAuth providers
        enabled=True,
        session_metadata=request.credentials or {},
        tenant_id=tenant_id,
    )
    db.add(integration)
    await db.commit()
    await db.refresh(integration)
    
    return {
        "id": integration.id,
        "provider": integration.provider,
        "message": f"Calendar {request.provider} setup completed"
    }


@router.get("/events")
async def get_events(
    provider: str = Query("google"),
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    max_results: int = Query(50, ge=1, le=250),
    integration_id: Optional[UUID] = None,
    calendar_service: CalendarService = Depends(get_calendar_service),
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Get calendar events"""
    if provider == "google":
        # Get integration from database (filtered by tenant)
        if integration_id:
            result = await db.execute(
                select(Integration)
                .where(Integration.id == integration_id)
                .where(Integration.tenant_id == tenant_id)
                .where(Integration.provider == "google")
                .where(Integration.service_type == "calendar")
                .where(Integration.enabled == True)
            )
            integration = result.scalar_one_or_none()
            
            if not integration:
                raise HTTPException(status_code=404, detail="Integration not found or disabled")
            
            # Decrypt and setup if not already done
            from app.core.config import settings
            try:
                credentials = _decrypt_credentials(
                    integration.credentials_encrypted,
                    settings.credentials_encryption_key
                )
                await calendar_service.setup_google(credentials, str(integration_id))
            except IntegrationAuthError as exc:
                raise HTTPException(
                    status_code=401,
                    detail={
                        "message": "Autorizzazione Google Calendar scaduta o revocata.",
                        "reason": exc.reason,
                    },
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc))
        
        # Fetch events
        try:
            events = await calendar_service.get_google_events(
                start_time=start_time,
                end_time=end_time,
                max_results=max_results,
                integration_id=str(integration_id) if integration_id else None,
            )
        except IntegrationAuthError as exc:
            raise HTTPException(
                status_code=401,
                detail={
                    "message": "Autorizzazione Google Calendar scaduta o revocata.",
                    "reason": exc.reason,
                },
            )
        
        return {
            "provider": provider,
            "events": events,
            "count": len(events),
        }
    
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Provider {provider} not yet implemented"
        )


@router.post("/query")
async def query_events_natural(
    request: CalendarQueryRequest,
    calendar_service: CalendarService = Depends(get_calendar_service),
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Query calendar events using natural language"""
    # Parse date range from natural language
    start_time, end_time = _date_parser.parse_query(request.query)
    
    if not start_time or not end_time:
        # Default to next 7 days if can't parse
        start_time = datetime.now()
        end_time = start_time + timedelta(days=7)
    
    # Get events using parsed dates - call get_events directly
    try:
        if request.provider == "google":
            # Get integration if provided (filtered by tenant)
            if request.integration_id:
                result = await db.execute(
                    select(Integration)
                    .where(Integration.id == request.integration_id)
                    .where(Integration.tenant_id == tenant_id)
                    .where(Integration.provider == "google")
                    .where(Integration.service_type == "calendar")
                    .where(Integration.enabled == True)
                )
                integration = result.scalar_one_or_none()
                
                if not integration:
                    raise HTTPException(status_code=404, detail="Integration not found or disabled")
                
                # Decrypt and setup if needed
                from app.core.config import settings
                try:
                    credentials = _decrypt_credentials(
                        integration.credentials_encrypted,
                        settings.credentials_encryption_key
                    )
                    await calendar_service.setup_google(credentials, str(request.integration_id))
                except IntegrationAuthError as exc:
                    raise HTTPException(
                        status_code=401,
                        detail={
                            "message": "Autorizzazione Google Calendar scaduta o revocata.",
                            "reason": exc.reason,
                        },
                    )
                except Exception as exc:
                    raise HTTPException(status_code=400, detail=str(exc))
            
            # Fetch events
            try:
                events = await calendar_service.get_google_events(
                    start_time=start_time,
                    end_time=end_time,
                    max_results=50,
                    integration_id=str(request.integration_id) if request.integration_id else None,
                )
            except IntegrationAuthError as exc:
                raise HTTPException(
                    status_code=401,
                    detail={
                        "message": "Autorizzazione Google Calendar scaduta o revocata.",
                        "reason": exc.reason,
                    },
                )
            
            return {
                "query": request.query,
                "parsed_start": start_time.isoformat(),
                "parsed_end": end_time.isoformat(),
                "provider": request.provider,
                "events": events,
                "count": len(events),
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Provider {request.provider} not yet implemented"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error querying calendar: {str(e)}"
        )


@router.get("/integrations")
async def list_calendar_integrations(
    provider: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """List calendar integrations for current user (only user_calendar, not service_calendar)"""
    query = (
        select(Integration)
        .where(Integration.service_type == "calendar")
        .where(Integration.purpose == "user_calendar")  # Only user integrations
        .where(Integration.tenant_id == tenant_id)
        .where(Integration.user_id == current_user.id)  # Only current user's integrations
    )
    
    if provider:
        query = query.where(Integration.provider == provider)
    
    result = await db.execute(query)
    integrations = result.scalars().all()
    
    return {
        "integrations": [
            {
                "id": str(integration.id),
                "provider": integration.provider,
                "enabled": integration.enabled,
                "purpose": integration.purpose,
            }
            for integration in integrations
        ]
    }


@router.get("/admin/integrations")
async def list_service_calendar_integrations(
    provider: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(require_admin),  # Only admin can list service integrations
):
    """List service calendar integrations (admin only) - for system-level operations"""
    query = (
        select(Integration)
        .where(Integration.service_type == "calendar")
        .where(Integration.purpose == "service_calendar")  # Only service integrations
        .where(Integration.tenant_id == tenant_id)
        .where(Integration.user_id.is_(None))  # Service integrations have no user_id
    )
    
    if provider:
        query = query.where(Integration.provider == provider)
    
    result = await db.execute(query)
    integrations = result.scalars().all()
    
    return {
        "integrations": [
            {
                "id": str(integration.id),
                "provider": integration.provider,
                "enabled": integration.enabled,
                "purpose": integration.purpose,
            }
            for integration in integrations
        ]
    }


@router.delete("/integrations/{integration_id}")
async def delete_calendar_integration(
    integration_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Delete a calendar integration (for current tenant)"""
    result = await db.execute(
        select(Integration)
        .where(
            Integration.id == integration_id,
            Integration.tenant_id == tenant_id,
            Integration.service_type == "calendar"
        )
    )
    integration = result.scalar_one_or_none()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    # Delete using session
    await db.delete(integration)
    await db.commit()
    
    return {"message": "Integration deleted successfully"}


@router.post("/admin/service")
async def create_service_calendar_integration(
    request: CalendarSetupRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(require_admin),  # Only admin can create service integrations
):
    """
    Create a service calendar integration (admin only).
    Service integrations are used for system-level calendar operations.
    """
    if request.provider == "google":
        raise HTTPException(
            status_code=400,
            detail="Use OAuth flow for Google calendar. Service integrations should be created via OAuth with user_id=NULL."
        )
    
    # Validate purpose and user_id consistency
    validate_integration_purpose("service_calendar", None, current_user, is_admin_required=True)
    
    # Create service integration (user_id = NULL, purpose = service_calendar)
    integration = Integration(
        provider=request.provider,
        service_type="calendar",
        purpose="service_calendar",  # Service integration
        enabled=True,
        session_metadata=request.credentials or {},
        tenant_id=tenant_id,
        user_id=None,  # Service integrations have no user_id
    )
    db.add(integration)
    await db.commit()
    await db.refresh(integration)
    
    return {
        "id": integration.id,
        "provider": integration.provider,
        "purpose": integration.purpose,
        "message": f"Service calendar integration for {request.provider} created"
    }
