"""
Email Poller - Checks for new emails and creates proactive notifications
"""
import logging
import json
import base64
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from cryptography.fernet import Fernet

from app.models.database import Integration, User
from app.services.email_service import EmailService
from app.services.exceptions import IntegrationAuthError
from app.services.notification_service import NotificationService
from app.core.config import settings

logger = logging.getLogger(__name__)


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


class EmailPoller:
    """Polls email integrations for new messages and creates notifications"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.email_service = EmailService()
        self.notification_service = NotificationService(db)
        # Track last checked email ID per integration per evitare duplicati
        self._last_email_ids: Dict[str, str] = {}
    
    async def check_new_emails(self) -> List[Dict[str, Any]]:
        """
        Check all Gmail integrations for new emails.
        Returns list of events created.
        """
        events_created = []
        
        # Get all active Gmail integrations
        result = await self.db.execute(
            select(Integration).where(
                Integration.provider == "google",
                Integration.service_type == "email",
                Integration.enabled == True
            )
        )
        integrations = result.scalars().all()
        
        if not integrations:
            logger.debug("No active Gmail integrations found")
            return events_created
        
        logger.info(f"Checking {len(integrations)} Gmail integrations for new emails")
        
        for integration in integrations:
            try:
                events = await self._check_integration_emails(integration)
                events_created.extend(events)
            except Exception as e:
                logger.error(
                    f"Error checking emails for integration {integration.id}: {e}",
                    exc_info=True
                )
                # Continue con altre integrazioni anche se una fallisce
                continue
        
        return events_created
    
    async def _check_integration_emails(self, integration: Integration) -> List[Dict[str, Any]]:
        """Check emails for a specific integration"""
        events_created = []
        
        # Setup email service per questa integrazione
        try:
            # Decrypt credentials
            credentials = _decrypt_credentials(
                integration.credentials_encrypted,
                settings.credentials_encryption_key
            )
            
            # Setup Gmail service
            await self.email_service.setup_gmail(
                credentials,
                integration_id=str(integration.id)
            )
        except IntegrationAuthError as e:
            logger.warning(f"Integration {integration.id} auth failed: {e}")
            return events_created
        except Exception as e:
            logger.error(f"Error setting up Gmail for integration {integration.id}: {e}")
            return events_created
        
        # Get last checked email ID per questa integrazione
        integration_key = str(integration.id)
        last_email_id = self._last_email_ids.get(integration_key)
        
        # Query per nuove email (solo non lette per ora)
        try:
            # Get unread emails from last 24 hours
            messages = await self.email_service.get_gmail_messages(
                max_results=20,
                query="is:unread newer_than:1d",
                integration_id=str(integration.id),
                include_body=False  # Non serve il body per notifiche
            )
        except Exception as e:
            logger.error(f"Error fetching emails for integration {integration.id}: {e}")
            return events_created
        
        if not messages:
            logger.debug(f"No new emails for integration {integration.id}")
            return events_created
        
        # Filtra solo email nuove (non già controllate)
        new_messages = []
        if last_email_id:
            # Trova l'indice dell'ultima email controllata
            for i, msg in enumerate(messages):
                if msg.get("id") == last_email_id:
                    # Tutte le email dopo questa sono nuove
                    new_messages = messages[:i]
                    break
            else:
                # Ultima email non trovata, tutte sono nuove
                new_messages = messages
        else:
            # Prima volta che controlliamo, prendi solo le più recenti
            new_messages = messages[:5]  # Limita a 5 per evitare spam
        
        if not new_messages:
            logger.debug(f"No new emails since last check for integration {integration.id}")
            return events_created
        
        # Aggiorna last_email_id con la più recente
        if new_messages:
            self._last_email_ids[integration_key] = new_messages[0].get("id")
        
        # Crea notifiche per ogni nuova email
        for msg in new_messages:
            try:
                # Determina priorità basata su mittente e contenuto
                priority = self._determine_email_priority(msg)
                
                # Crea notifica (controlla duplicati basati su email_id)
                email_id = msg.get("id")
                notification = await self.notification_service.create_notification(
                    type="email_received",
                    urgency=priority,
                    content={
                        "email_id": email_id,
                        "from": msg.get("from"),
                        "subject": msg.get("subject"),
                        "snippet": msg.get("snippet", "")[:200],  # Primi 200 caratteri
                        "date": msg.get("date"),
                        "integration_id": str(integration.id),
                    },
                    session_id=None,  # Notifica globale, non legata a sessione
                    tenant_id=integration.tenant_id,
                    check_duplicate={"key": "email_id", "value": email_id} if email_id else None,
                )
                
                # Skip se notifica duplicata
                if not notification:
                    logger.debug(f"Skipping duplicate notification for email {email_id}")
                    continue
                
                # Aggiungi user_id se l'integrazione è per utente specifico
                if integration.user_id:
                    # Aggiorna notification con user_id (se il modello lo supporta)
                    # Per ora usiamo solo tenant_id
                    pass
                
                events_created.append({
                    "type": "email_received",
                    "priority": priority,
                    "notification_id": str(notification.id),
                    "email": msg.get("from"),
                    "subject": msg.get("subject"),
                })
                
                logger.info(
                    f"Created notification for new email from {msg.get('from')} "
                    f"(priority: {priority})"
                )
            except Exception as e:
                logger.error(f"Error creating notification for email {msg.get('id')}: {e}")
                continue
        
        return events_created
    
    def _determine_email_priority(self, email: Dict[str, Any]) -> str:
        """
        Determina priorità email basata su:
        - Mittente (contatti importanti?)
        - Oggetto (parole chiave urgenti?)
        - Data (molto recente?)
        """
        subject = (email.get("subject") or "").lower()
        from_addr = (email.get("from") or "").lower()
        
        # Parole chiave urgenti
        urgent_keywords = ["urgent", "urgente", "asap", "immediate", "immediato", "important", "importante"]
        if any(keyword in subject for keyword in urgent_keywords):
            return "high"
        
        # Email molto recente (< 5 minuti) potrebbe essere importante
        email_date = email.get("date")
        if email_date:
            try:
                if isinstance(email_date, str):
                    from dateutil import parser
                    email_date = parser.parse(email_date)
                if isinstance(email_date, datetime):
                    age = datetime.now(timezone.utc) - email_date.replace(tzinfo=timezone.utc)
                    if age < timedelta(minutes=5):
                        return "medium"
            except Exception:
                pass
        
        # Default: low priority
        return "low"

