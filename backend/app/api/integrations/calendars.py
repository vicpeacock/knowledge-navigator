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
):
    """Start OAuth2 flow for Google Calendar"""
    from app.core.config import settings
    
    if not settings.google_client_id:
        raise HTTPException(
            status_code=400,
            detail="Google OAuth credentials not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env"
        )
    
    try:
        flow = calendar_service.create_google_oauth_flow(
            state=str(integration_id) if integration_id else None
        )
        authorization_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
        )
        return {"authorization_url": authorization_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating OAuth flow: {str(e)}")


@router.get("/oauth/callback")
async def oauth_callback(
    code: str,
    state: Optional[str] = None,
    calendar_service: CalendarService = Depends(get_calendar_service),
    db: AsyncSession = Depends(get_db),
):
    """OAuth2 callback for Google Calendar"""
    from app.core.config import settings
    
    try:
        flow = calendar_service.create_google_oauth_flow(state=state)
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
                    flow = calendar_service.create_google_oauth_flow(state=state, scopes=new_scopes)
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
        
        integration_id = None
        if state:
            try:
                integration_id = UUID(state)
            except (ValueError, TypeError):
                # State is not a valid UUID, treat as new integration
                integration_id = None
        
        if integration_id:
            # Update existing integration
            result = await db.execute(
                select(Integration).where(Integration.id == integration_id)
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
                await db.commit()
            else:
                raise HTTPException(status_code=404, detail="Integration not found")
        else:
            # Create new integration
            if not credentials.get("refresh_token"):
                raise HTTPException(
                    status_code=400,
                    detail="L'autorizzazione non ha fornito il refresh token. Concedi tutti i permessi richiesti e riprova."
                )
            encrypted = _encrypt_credentials(credentials, settings.credentials_encryption_key)
            integration = Integration(
                provider="google",
                service_type="calendar",
                credentials_encrypted=encrypted,
                enabled=True,
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
        frontend_url = "http://localhost:3003"  # Can be made configurable
        return RedirectResponse(
            url=f"{frontend_url}/integrations?success=true&integration_id={integration_id}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in OAuth callback: {str(e)}")


@router.post("/setup")
async def setup_calendar(
    request: CalendarSetupRequest,
    db: AsyncSession = Depends(get_db),
):
    """Setup calendar integration (for non-OAuth providers)"""
    if request.provider == "google":
        # For Google, use OAuth flow instead
        raise HTTPException(
            status_code=400,
            detail="Use /oauth/authorize endpoint for Google Calendar setup"
        )
    
    # For other providers, store credentials directly
    integration = Integration(
        provider=request.provider,
        service_type="calendar",
        enabled=True,
        session_metadata=request.credentials or {},
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
):
    """Get calendar events"""
    if provider == "google":
        # Get integration from database
        if integration_id:
            result = await db.execute(
                select(Integration)
                .where(Integration.id == integration_id)
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
            # Get integration if provided
            if request.integration_id:
                result = await db.execute(
                    select(Integration)
                    .where(Integration.id == request.integration_id)
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
):
    """List all calendar integrations"""
    query = select(Integration).where(Integration.service_type == "calendar")
    
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
            }
            for integration in integrations
        ]
    }


@router.delete("/integrations/{integration_id}")
async def delete_calendar_integration(
    integration_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a calendar integration"""
    result = await db.execute(
        select(Integration)
        .where(Integration.id == integration_id)
        .where(Integration.service_type == "calendar")
    )
    integration = result.scalar_one_or_none()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    # Delete using session
    await db.delete(integration)
    await db.commit()
    
    return {"message": "Integration deleted successfully"}
