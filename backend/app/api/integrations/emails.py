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
from app.services.email_service import EmailService, IntegrationAuthError
from app.core.ollama_client import OllamaClient
from app.core.dependencies import get_ollama_client
from app.core.tenant_context import get_tenant_id
from app.core.user_context import get_current_user, require_admin
from app.core.integration_validation import validate_integration_purpose
from app.models.database import User  # type: ignore  # for type hints only
from cryptography.fernet import Fernet
import base64
import json

router = APIRouter()

# Global email service instance
_email_service = EmailService()


def get_email_service() -> EmailService:
    """Dependency to get email service"""
    return _email_service


def _encrypt_credentials(credentials: Dict[str, Any], key: str) -> str:
    """Encrypt credentials for storage"""
    try:
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


class EmailSetupRequest(BaseModel):
    provider: str  # google, apple, microsoft
    credentials: Optional[Dict[str, Any]] = None


class EmailQueryRequest(BaseModel):
    query: str  # Gmail query string (e.g., "is:unread", "from:example@gmail.com")
    integration_id: Optional[UUID] = None


@router.get("/oauth/authorize")
async def authorize_gmail(
    integration_id: Optional[UUID] = None,
    service_integration: bool = Query(False, description="Create service integration (admin only, for system communications)"),
    email_service: EmailService = Depends(get_email_service),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """Start OAuth2 flow for Gmail
    
    Args:
        integration_id: Optional integration ID to update existing integration
        service_integration: If True, create service integration (admin only, user_id=NULL, purpose=service_email)
    """
    from app.core.config import settings
    
    if not settings.google_client_id:
        raise HTTPException(
            status_code=400,
            detail="Google OAuth credentials not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env"
        )
    
    # Only admin can create service integrations
    if service_integration and current_user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only administrators can create service integrations"
        )
    
    try:
        # Encode state with integration_id, user_id, and service_integration flag
        state_payload = {
            "integration_id": str(integration_id) if integration_id else None,
            "user_id": None if service_integration else str(current_user.id),  # NULL for service integrations
            "service_integration": service_integration,
        }
        import json as json_lib
        import base64

        state_str = base64.urlsafe_b64encode(
            json_lib.dumps(state_payload).encode("utf-8")
        ).decode("utf-8")

        flow = email_service.create_gmail_oauth_flow()
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
    state: Optional[str] = None,
    email_service: EmailService = Depends(get_email_service),
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """OAuth2 callback for Gmail"""
    from app.core.config import settings
    
    try:
        flow = email_service.create_gmail_oauth_flow()
        flow.fetch_token(code=code)
        
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
        service_integration: bool = False
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
                
                logger.info(f"OAuth callback (Email) - Decoded state: integration_id={integration_id_str}, user_id={user_id_str}, service_integration={service_integration}")
                
                if integration_id_str:
                    integration_id = UUID(integration_id_str)
                if user_id_str:
                    user_id = UUID(user_id_str)
                    logger.info(f"OAuth callback (Email) - Setting user_id={user_id} for new integration")
                elif service_integration:
                    # Service integrations have user_id = NULL
                    user_id = None
                    logger.info(f"OAuth callback (Email) - Service integration, user_id=NULL")
            except Exception as e:
                logger.warning(f"OAuth callback (Email) - Failed to decode state as JSON: {e}, trying as UUID")
                # Fallback: treat state as raw UUID (old behavior - deprecated)
                try:
                    integration_id = UUID(state)
                    # Old format: state was just integration_id UUID, no user_id
                    # This is deprecated - we need user_id from state
                    logger.warning(f"OAuth callback (Email) - State is old format UUID (no user_id). This is deprecated.")
                    user_id = None  # Will need to be set manually or from integration
                except (ValueError, TypeError):
                    integration_id = None
                    # Cannot get user_id without state - this is an error
                    logger.error(f"OAuth callback (Email) - State is not a valid UUID and cannot be decoded: {state}")
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid state parameter. Please try connecting again."
                    )
        
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
                # Questo risolve il problema delle integrazioni create senza user_id
                if user_id and (not integration.user_id or integration.user_id != user_id):
                    logger.info(f"OAuth callback (Email) - Updating user_id for integration {integration_id}: {integration.user_id} -> {user_id}")
                    integration.user_id = user_id
                    # Ensure purpose is set correctly for user integration
                    if not integration.purpose or not integration.purpose.startswith("user_"):
                        integration.purpose = "user_email"
                        logger.info(f"OAuth callback (Email) - Updated purpose to user_email for integration {integration_id}")
                
                await db.commit()
                await db.refresh(integration)
            else:
                raise HTTPException(status_code=404, detail="Integration not found")
        else:
            if not credentials.get("refresh_token"):
                raise HTTPException(
                    status_code=400,
                    detail="L'autorizzazione non ha fornito il refresh token. Concedi tutti i permessi richiesti e riprova."
                )
            # For service integrations, user_id is NULL (allowed)
            # For user integrations, user_id is required
            if not service_integration and not user_id:
                logger.error(f"OAuth callback (Email) - Cannot create new user integration: no user_id in state")
                raise HTTPException(
                    status_code=400,
                    detail="Invalid state parameter: user_id is required for user integrations. Please try connecting again."
                )
            encrypted = _encrypt_credentials(credentials, settings.credentials_encryption_key)
            # Determine purpose based on service_integration flag
            purpose = "service_email" if service_integration else "user_email"
            # Validate purpose and user_id consistency
            validate_integration_purpose(purpose, user_id)
            integration = Integration(
                provider="google",
                service_type="email",
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
        
        # Get Google user email from ID token (if available) or access token
        google_email = None
        try:
            # First, try to get email from ID token (more reliable)
            id_token = getattr(flow.credentials, 'id_token', None)
            if id_token:
                try:
                    # Decode JWT ID token (format: header.payload.signature)
                    import base64 as b64
                    parts = id_token.split('.')
                    if len(parts) >= 2:
                        # Decode payload (base64url)
                        payload_b64 = parts[1]
                        # Add padding if needed
                        padding = 4 - len(payload_b64) % 4
                        if padding != 4:
                            payload_b64 += '=' * padding
                        payload_bytes = b64.urlsafe_b64decode(payload_b64)
                        payload = json_lib.loads(payload_bytes.decode('utf-8'))
                        google_email = payload.get("email")
                        if google_email:
                            logger.info(f"📧 Retrieved Google email from ID token: {google_email}")
                except Exception as id_token_error:
                    logger.warning(f"⚠️  Could not decode ID token: {id_token_error}")
            
            # Fallback: try to get email from access token via API
            if not google_email:
                import httpx
                access_token = credentials.get("token")
                if access_token:
                    async with httpx.AsyncClient() as client:
                        response = await client.get(
                            "https://www.googleapis.com/oauth2/v2/userinfo",
                            headers={"Authorization": f"Bearer {access_token}"},
                            timeout=5.0
                        )
                        if response.status_code == 200:
                            user_info = response.json()
                            google_email = user_info.get("email")
                            if google_email:
                                logger.info(f"📧 Retrieved Google email from API: {google_email}")
        except Exception as email_error:
            logger.warning(f"⚠️  Could not retrieve Google email during OAuth callback: {email_error}")
        
        # Save Google email in session_metadata if available
        # Get the integration (it should exist by now)
        integration = await db.get(Integration, integration_id)
        if integration and google_email:
            session_metadata = integration.session_metadata or {}
            if "oauth_user_emails" not in session_metadata:
                session_metadata["oauth_user_emails"] = {}
            # Use user_id if available, otherwise use integration.user_id
            target_user_id = user_id or integration.user_id
            if target_user_id:
                session_metadata["oauth_user_emails"][str(target_user_id)] = google_email
                integration.session_metadata = session_metadata
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(integration, "session_metadata")
                await db.commit()
                logger.info(f"💾 Saved Google email to integration metadata for user {target_user_id}: {google_email}")
            else:
                logger.warning(f"⚠️  Cannot save Google email: no user_id available (user_id={user_id}, integration.user_id={integration.user_id})")
        elif not google_email:
            logger.warning(f"⚠️  No Google email retrieved during OAuth callback")
        elif not integration:
            logger.error(f"❌ Integration {integration_id} not found after creation")
        
        # Setup email service
        try:
            await email_service.setup_gmail(credentials, str(integration_id))
        except IntegrationAuthError as exc:
            raise HTTPException(
                status_code=401,
                detail={
                    "message": "Autorizzazione Gmail non valida.",
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


@router.get("/messages")
async def get_messages(
    provider: str = Query("gmail"),
    max_results: int = Query(10, ge=1, le=50),
    query: Optional[str] = None,
    include_body: bool = Query(False),
    integration_id: Optional[UUID] = None,
    email_service: EmailService = Depends(get_email_service),
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Get email messages"""
    if provider == "gmail":
        if integration_id:
            result = await db.execute(
                select(Integration)
                .where(Integration.id == integration_id)
                .where(Integration.tenant_id == tenant_id)
                .where(Integration.provider == "google")
                .where(Integration.service_type == "email")
                .where(Integration.enabled == True)
            )
            integration = result.scalar_one_or_none()
            
            if not integration:
                raise HTTPException(status_code=404, detail="Integration not found or disabled")
            
            from app.core.config import settings
            try:
                credentials = _decrypt_credentials(
                    integration.credentials_encrypted,
                    settings.credentials_encryption_key
                )
                await email_service.setup_gmail(credentials, str(integration_id))
            except IntegrationAuthError as exc:
                raise HTTPException(
                    status_code=401,
                    detail={
                        "message": "Autorizzazione Gmail scaduta o revocata.",
                        "reason": exc.reason,
                    },
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc))
        
        try:
            messages = await email_service.get_gmail_messages(
                max_results=max_results,
                query=query,
                integration_id=str(integration_id) if integration_id else None,
                include_body=include_body,
            )
        except IntegrationAuthError as exc:
            raise HTTPException(
                status_code=401,
                detail={
                    "message": "Autorizzazione Gmail scaduta o revocata.",
                    "reason": exc.reason,
                },
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        
        return {
            "provider": provider,
            "messages": messages,
            "count": len(messages),
        }
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Provider {provider} not yet implemented"
        )


@router.post("/summarize")
async def summarize_important_emails(
    integration_id: UUID,
    max_emails: int = Query(5, ge=1, le=10),
    ollama: OllamaClient = Depends(get_ollama_client),
    email_service: EmailService = Depends(get_email_service),
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Summarize important unread emails (for current tenant)"""
    from app.core.config import settings
    
    # Get integration (filtered by tenant)
    result = await db.execute(
        select(Integration)
        .where(Integration.id == integration_id)
        .where(Integration.tenant_id == tenant_id)
        .where(Integration.provider == "google")
        .where(Integration.service_type == "email")
        .where(Integration.enabled == True)
    )
    integration = result.scalar_one_or_none()
    
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    
    # Decrypt and setup
    try:
        credentials = _decrypt_credentials(
            integration.credentials_encrypted,
            settings.credentials_encryption_key
        )
        await email_service.setup_gmail(credentials, str(integration_id))
    except IntegrationAuthError as exc:
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Autorizzazione Gmail scaduta o revocata.",
                "reason": exc.reason,
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    
    # Get unread emails
    try:
        emails = await email_service.get_gmail_messages(
            max_results=max_emails,
            query="is:unread",
            integration_id=str(integration_id),
            include_body=True,
        )
    except IntegrationAuthError as exc:
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Autorizzazione Gmail scaduta o revocata.",
                "reason": exc.reason,
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    
    if not emails:
        return {
            "summary": "Nessuna email non letta trovata.",
            "emails_count": 0,
        }
    
    # Create summary prompt
    email_summaries = []
    for email in emails:
        email_text = f"From: {email['from']}\nSubject: {email['subject']}\n"
        if email.get('body'):
            # Truncate body if too long
            body = email['body'][:1000] if len(email.get('body', '')) > 1000 else email.get('body', '')
            email_text += f"Body: {body}\n"
        else:
            email_text += f"Snippet: {email.get('snippet', '')}\n"
        email_summaries.append(email_text)
    
    all_emails_text = "\n\n---\n\n".join(email_summaries)
    
    summary_prompt = f"""Riassumi le seguenti email non lette in modo conciso e utile. 
Indica per ciascuna: mittente, oggetto, e punti chiave del contenuto.

Email:
{all_emails_text}

Riassunto:"""
    
    # Generate summary using Ollama
    summary = await ollama.generate_with_context(
        prompt=summary_prompt,
        session_context=[],
        retrieved_memory=None,
    )
    
    return {
        "summary": summary,
        "emails_count": len(emails),
        "emails": [
            {
                "id": e["id"],
                "subject": e["subject"],
                "from": e["from"],
                "date": e["date"],
            }
            for e in emails
        ],
    }


@router.get("/integrations")
async def list_email_integrations(
    provider: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """List email integrations for current user (only user_email, not service_email)"""
    import logging
    logger = logging.getLogger(__name__)
    query = (
        select(Integration)
        .where(Integration.service_type == "email")
        .where(Integration.purpose == "user_email")  # Only user integrations
        .where(Integration.tenant_id == tenant_id)
        .where(Integration.user_id == current_user.id)  # Only current user's integrations
    )
    
    if provider:
        query = query.where(Integration.provider == provider)
    
    result = await db.execute(query)
    integrations = result.scalars().all()
    
    # Get Google email from session_metadata for each integration
    result_integrations = []
    for integration in integrations:
        integration_data = {
            "id": str(integration.id),
            "provider": integration.provider,
            "enabled": integration.enabled,
            "purpose": integration.purpose,
        }
        
        # Try to get Google email from session_metadata
        session_metadata = integration.session_metadata or {}
        oauth_user_emails = session_metadata.get("oauth_user_emails", {})
        if integration.user_id:
            google_email = oauth_user_emails.get(str(integration.user_id))
            if google_email:
                integration_data["google_email"] = google_email
                logger.debug(f"📧 Found Google email for integration {integration.id}: {google_email}")
            else:
                logger.debug(f"⚠️  No Google email found in metadata for integration {integration.id}, user {integration.user_id}")
                logger.debug(f"   Available user emails: {list(oauth_user_emails.keys())}")
        
        result_integrations.append(integration_data)
    
    return {
        "integrations": result_integrations
    }


@router.get("/admin/integrations")
async def list_service_email_integrations(
    provider: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(require_admin),  # Only admin can list service integrations
):
    """List service email integrations (admin only) - for system communications"""
    query = (
        select(Integration)
        .where(Integration.service_type == "email")
        .where(Integration.purpose == "service_email")  # Only service integrations
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
async def delete_email_integration(
    integration_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Delete an email integration (for current tenant)"""
    result = await db.execute(
        select(Integration)
        .where(
            Integration.id == integration_id,
            Integration.tenant_id == tenant_id,
            Integration.service_type == "email"
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
async def create_service_email_integration(
    request: EmailSetupRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(require_admin),  # Only admin can create service integrations
):
    """
    Create a service email integration (admin only).
    Service integrations are used for system messages (e.g., authentication emails).
    """
    if request.provider == "google":
        raise HTTPException(
            status_code=400,
            detail="Use OAuth flow for Google email. Service integrations should be created via OAuth with user_id=NULL."
        )
    
    # Validate purpose and user_id consistency
    validate_integration_purpose("service_email", None, current_user, is_admin_required=True)
    
    # Create service integration (user_id = NULL, purpose = service_email)
    integration = Integration(
        provider=request.provider,
        service_type="email",
        purpose="service_email",  # Service integration
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
        "message": f"Service email integration for {request.provider} created"
    }
