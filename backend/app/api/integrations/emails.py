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
from app.core.user_context import get_current_user
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


class EmailQueryRequest(BaseModel):
    query: str  # Gmail query string (e.g., "is:unread", "from:example@gmail.com")
    integration_id: Optional[UUID] = None


@router.get("/oauth/authorize")
async def authorize_gmail(
    integration_id: Optional[UUID] = None,
    email_service: EmailService = Depends(get_email_service),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user: User = Depends(get_current_user),
):
    """Start OAuth2 flow for Gmail"""
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
                
                logger.info(f"OAuth callback (Email) - Decoded state: integration_id={integration_id_str}, user_id={user_id_str}")
                
                if integration_id_str:
                    integration_id = UUID(integration_id_str)
                if user_id_str:
                    user_id = UUID(user_id_str)
                    logger.info(f"OAuth callback (Email) - Setting user_id={user_id} for new integration")
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
                
                # IMPORTANTE: Aggiorna anche user_id se mancante o se fornito nello state
                # Questo risolve il problema delle integrazioni create senza user_id
                if user_id and (not integration.user_id or integration.user_id != user_id):
                    logger.info(f"OAuth callback (Email) - Updating user_id for integration {integration_id}: {integration.user_id} -> {user_id}")
                    integration.user_id = user_id
                
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
            if not user_id:
                logger.error(f"OAuth callback (Email) - Cannot create new integration: no user_id in state")
                raise HTTPException(
                    status_code=400,
                    detail="Invalid state parameter: user_id is required. Please try connecting again."
                )
            encrypted = _encrypt_credentials(credentials, settings.credentials_encryption_key)
            integration = Integration(
                provider="google",
                service_type="email",
                credentials_encrypted=encrypted,
                enabled=True,
                tenant_id=tenant_id,
                user_id=user_id,
            )
            db.add(integration)
            await db.commit()
            await db.refresh(integration)
            integration_id = integration.id
        
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
        frontend_url = "http://localhost:3003"
        return RedirectResponse(
            url=f"{frontend_url}/integrations?success=true&integration_id={integration_id}"
        )
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
    """List email integrations for current user (and optional global ones)"""
    from sqlalchemy import or_

    query = (
        select(Integration)
        .where(Integration.service_type == "email")
        .where(Integration.tenant_id == tenant_id)
        # Per-user or global (user_id is NULL)
        .where(or_(Integration.user_id == current_user.id, Integration.user_id.is_(None)))
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
