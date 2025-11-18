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
from app.services.email_analyzer import EmailAnalyzer
from app.services.email_action_processor import EmailActionProcessor
from app.core.config import settings
from app.core.dependencies import get_ollama_client, get_memory_manager

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
        # Note: We no longer use _last_email_ids in-memory tracking
        # Instead, we check existing notifications in database to avoid duplicates
        
        # Initialize email analysis services if enabled
        self.email_analyzer = None
        self.email_action_processor = None
        if settings.email_analysis_enabled:
            try:
                ollama_client = get_ollama_client()
                memory_manager = get_memory_manager()
                self.email_analyzer = EmailAnalyzer(ollama_client=ollama_client)
                self.email_action_processor = EmailActionProcessor(
                    db=db,
                    ollama_client=ollama_client,
                    memory_manager=memory_manager,
                )
                logger.info("Email analysis services initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize email analysis services: {e}")
                logger.warning("Email analysis will be disabled")
    
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
        # Usa notifiche esistenti E sessioni create da email per deduplicare
        # Questo evita di ricreare notifiche anche se eliminate
        new_messages = []
        
        # Get all existing email notifications for this tenant
        from app.models.database import Notification as NotificationModel, Session as SessionModel
        existing_notifications_result = await self.db.execute(
            select(NotificationModel).where(
                NotificationModel.tenant_id == integration.tenant_id,
                NotificationModel.type == "email_received"
            )
        )
        existing_notifications = existing_notifications_result.scalars().all()
        existing_email_ids = set()
        for notif in existing_notifications:
            # Extract email_id from notification content
            content = notif.content
            if isinstance(content, dict):
                email_id = content.get("email_id")
            else:
                try:
                    email_id = content.get("email_id") if hasattr(content, 'get') else None
                except:
                    email_id = None
            if email_id:
                existing_email_ids.add(str(email_id))
        
        # Also check sessions created from emails (even if notification was deleted)
        existing_sessions_result = await self.db.execute(
            select(SessionModel).where(
                SessionModel.tenant_id == integration.tenant_id,
                SessionModel.session_metadata["source"].astext == "email_analysis"
            )
        )
        existing_sessions = existing_sessions_result.scalars().all()
        for session in existing_sessions:
            email_id = session.session_metadata.get("email_id") if isinstance(session.session_metadata, dict) else None
            if email_id:
                existing_email_ids.add(str(email_id))
        
        logger.debug(f"Found {len(existing_email_ids)} already processed emails (notifications + sessions) for tenant {integration.tenant_id}")
        
        # Filter out emails that already have notifications or sessions
        for msg in messages:
            email_id = msg.get("id")
            if email_id and str(email_id) not in existing_email_ids:
                new_messages.append(msg)
            else:
                logger.debug(f"Skipping email {email_id} - already processed (has notification or session)")
        
        if not new_messages:
            logger.debug(f"No new emails since last check for integration {integration.id} (all already have notifications)")
            return events_created
        
        logger.info(f"Found {len(new_messages)} new emails (filtered from {len(messages)} total) for integration {integration.id}")
        
        # Crea notifiche per ogni nuova email
        for msg in new_messages:
            try:
                email_id = msg.get("id")
                
                # Analyze email if analysis is enabled
                analysis = None
                if self.email_analyzer:
                    try:
                        # Analyze email using snippet (usually sufficient for action detection)
                        # Full body can be fetched later if needed for more detailed analysis
                        analysis = await self.email_analyzer.analyze_email(msg)
                        logger.info(
                            f"Email analysis for {email_id}: "
                            f"category={analysis.get('category')}, "
                            f"requires_action={analysis.get('requires_action')}, "
                            f"action_type={analysis.get('action_type')}, "
                            f"urgency={analysis.get('urgency')}"
                        )
                    except Exception as e:
                        logger.warning(f"Error analyzing email {email_id}: {e}")
                        analysis = None
                
                # Process action if analysis indicates action is required
                session_id = None
                if self.email_action_processor and analysis and analysis.get("requires_action"):
                    try:
                        if integration.user_id:
                            session_id = await self.email_action_processor.process_email_action(
                                email=msg,
                                analysis=analysis,
                                tenant_id=integration.tenant_id,
                                user_id=integration.user_id,
                            )
                            if session_id:
                                logger.info(f"Created automatic session {session_id} for email {email_id}")
                    except Exception as e:
                        logger.error(f"Error processing email action for {email_id}: {e}", exc_info=True)
                
                # Determina priorità basata su analisi o fallback a metodo tradizionale
                if analysis:
                    priority = analysis.get("urgency", "medium")
                else:
                    priority = self._determine_email_priority(msg)
                
                # Crea notifica (controlla duplicati basati su email_id)
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
                        "category": analysis.get("category") if analysis else "unknown",
                        "analysis": analysis,  # Store full analysis for reference
                        "auto_session_id": str(session_id) if session_id else None,
                    },
                    session_id=session_id,  # Link to auto-created session if exists
                    tenant_id=integration.tenant_id,
                    check_duplicate={"key": "email_id", "value": email_id} if email_id else None,
                )
                
                # Skip se notifica duplicata
                if not notification:
                    logger.debug(f"Skipping duplicate notification for email {email_id}")
                    continue
                
                events_created.append({
                    "type": "email_received",
                    "priority": priority,
                    "notification_id": str(notification.id),
                    "email": msg.get("from"),
                    "subject": msg.get("subject"),
                    "analysis": analysis,
                    "session_id": str(session_id) if session_id else None,
                })
                
                logger.info(
                    f"Created notification for new email from {msg.get('from')} "
                    f"(priority: {priority}, action: {analysis.get('action_type') if analysis else 'none'})"
                )
            except Exception as e:
                logger.error(f"Error creating notification for email {msg.get('id')}: {e}", exc_info=True)
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

