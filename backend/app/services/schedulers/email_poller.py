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
        
        # Query per nuove email (solo non lette per ora)
        try:
            # Get unread emails from last 24 hours
            logger.info(f"🔍 Checking for new emails for integration {integration.id} (tenant: {integration.tenant_id})")
            logger.info(f"📧 Query: 'is:unread newer_than:1d', max_results: 50")
            
            messages = await self.email_service.get_gmail_messages(
                max_results=50,  # Increased to catch more emails
                query="is:unread newer_than:1d",
                integration_id=str(integration.id),
                include_body=False  # Non serve il body per notifiche
            )
            logger.info(f"📧 Gmail API returned {len(messages)} unread emails (last 24h)")
            
            # Log first few email IDs and subjects for debugging
            if messages:
                logger.info(f"📋 First 3 emails from Gmail:")
                for i, msg in enumerate(messages[:3], 1):
                    logger.info(f"   {i}. ID: {msg.get('id')}, Subject: {msg.get('subject', 'No subject')[:60]}, From: {msg.get('from', 'Unknown')[:40]}")
            
            # If no results, try without time filter (just unread)
            if not messages:
                logger.warning("⚠️  No emails with time filter, trying 'is:unread' without time limit...")
                messages = await self.email_service.get_gmail_messages(
                    max_results=50,
                    query="is:unread",
                    integration_id=str(integration.id),
                    include_body=False
                )
                logger.info(f"📧 Gmail API query 'is:unread' returned {len(messages)} emails")
                if messages:
                    logger.info(f"📋 First 3 emails (no time filter):")
                    for i, msg in enumerate(messages[:3], 1):
                        logger.info(f"   {i}. ID: {msg.get('id')}, Subject: {msg.get('subject', 'No subject')[:60]}")
        except Exception as e:
            logger.error(f"❌ Error fetching emails for integration {integration.id}: {e}", exc_info=True)
            return events_created
        
        if not messages:
            logger.info(f"ℹ️  No unread emails found for integration {integration.id}")
            return events_created
        
        # Filtra solo email nuove (non già controllate)
        # Usa notifiche esistenti E sessioni create da email per deduplicare
        # Questo evita di ricreare notifiche anche se eliminate
        new_messages = []
        
        # Get all existing email notifications for this tenant AND this integration
        # IMPORTANTE: Ogni integrazione deve controllare solo le proprie notifiche per la deduplicazione
        from app.models.database import Notification as NotificationModel, Session as SessionModel
        existing_notifications_result = await self.db.execute(
            select(NotificationModel).where(
                NotificationModel.tenant_id == integration.tenant_id,
                NotificationModel.type == "email_received",
                NotificationModel.content["integration_id"].astext == str(integration.id)  # Filtra per integration_id
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
        
        # Also check sessions created from emails by THIS integration's user (even if notification was deleted)
        # IMPORTANTE: Controlla solo le sessioni create dall'utente di questa integrazione
        # IMPORTANTE: Include anche sessioni cancellate/archiviate per evitare di ricrearle
        try:
            if integration.user_id:
                existing_sessions_result = await self.db.execute(
                    select(SessionModel).where(
                        SessionModel.tenant_id == integration.tenant_id,
                        SessionModel.user_id == integration.user_id,  # Filtra per user_id dell'integrazione
                        SessionModel.session_metadata["source"].astext == "email_analysis"
                        # NON filtrare per status - include anche "deleted" e "archived" per deduplicazione
                    )
                )
                existing_sessions = existing_sessions_result.scalars().all()
                logger.debug(f"Found {len(existing_sessions)} sessions created from emails by user {integration.user_id} (including deleted/archived)")
                for session in existing_sessions:
                    # Extract email_id from session metadata
                    metadata = session.session_metadata
                    if isinstance(metadata, dict):
                        email_id = metadata.get("email_id")
                    else:
                        # JSONB field might need different access
                        try:
                            email_id = metadata.get("email_id") if hasattr(metadata, 'get') else None
                        except:
                            email_id = None
                    if email_id:
                        existing_email_ids.add(str(email_id))
                        logger.debug(f"  - Session {session.id} (status: {session.status}) has email_id: {email_id}")
            else:
                logger.debug("Integration has no user_id, skipping session deduplication check")
                existing_sessions = []
        except Exception as e:
            logger.warning(f"⚠️  Error checking sessions for email deduplication: {e}")
            # Continue without session check - notifications check should be enough
            existing_sessions = []
        
        logger.info(f"📊 Deduplication: Found {len(existing_email_ids)} already processed emails (notifications: {len([n for n in existing_notifications])}, sessions: {len(existing_sessions) if 'existing_sessions' in locals() else 0})")
        
        # Log all email IDs from Gmail for debugging
        gmail_email_ids = [msg.get("id") for msg in messages if msg.get("id")]
        logger.debug(f"📧 Email IDs from Gmail: {gmail_email_ids[:5]}... (showing first 5)")
        
        # Filter out emails that already have notifications or sessions
        for msg in messages:
            email_id = msg.get("id")
            if not email_id:
                logger.warning(f"⚠️  Email message missing ID: {msg}")
                continue
                
            if str(email_id) not in existing_email_ids:
                new_messages.append(msg)
                logger.debug(f"✅ New email found: {email_id} - {msg.get('subject', 'No subject')[:50]}")
            else:
                logger.debug(f"⏭️  Skipping email {email_id} - already processed (has notification or session)")
        
        if not new_messages:
            logger.info(f"ℹ️  No new emails to process for integration {integration.id} (all {len(messages)} emails already have notifications/sessions)")
            return events_created
        
        logger.info(f"🎯 Processing {len(new_messages)} new emails (filtered from {len(messages)} total) for integration {integration.id}")
        
        # Check if this email is a reply to an email sent by the assistant
        # Get all thread_ids from sessions where assistant sent emails
        sent_thread_ids = set()
        try:
            if integration.user_id:
                sent_sessions_result = await self.db.execute(
                    select(SessionModel).where(
                        SessionModel.tenant_id == integration.tenant_id,
                        SessionModel.user_id == integration.user_id,
                        SessionModel.session_metadata["sent_email_threads"].isnot(None)
                    )
                )
                sent_sessions = sent_sessions_result.scalars().all()
                for session in sent_sessions:
                    metadata = session.session_metadata
                    if isinstance(metadata, dict):
                        threads = metadata.get("sent_email_threads", [])
                        if isinstance(threads, list):
                            sent_thread_ids.update(str(t) for t in threads)
                logger.info(f"📧 Found {len(sent_thread_ids)} tracked thread_ids from assistant-sent emails")
        except Exception as e:
            logger.warning(f"⚠️  Error checking sent email threads: {e}")
        
        # Crea notifiche per ogni nuova email
        for msg in new_messages:
            try:
                email_id = msg.get("id")
                thread_id = msg.get("thread_id", "")
                
                # Check if this email is a reply to an assistant-sent email
                is_reply_to_assistant = False
                if thread_id and str(thread_id) in sent_thread_ids:
                    is_reply_to_assistant = True
                    logger.info(f"📧 Email {email_id} is a reply to assistant-sent email (thread_id: {thread_id})")
                
                # Analyze email if analysis is enabled
                analysis = None
                if self.email_analyzer:
                    try:
                        # Analyze email using snippet (usually sufficient for action detection)
                        # Full body can be fetched later if needed for more detailed analysis
                        analysis = await self.email_analyzer.analyze_email(msg)
                        
                        # If this is a reply to assistant-sent email, always mark as requiring action
                        if is_reply_to_assistant:
                            analysis["requires_action"] = True
                            if analysis.get("urgency") == "low":
                                analysis["urgency"] = "medium"  # Upgrade urgency
                            analysis["is_reply_to_assistant"] = True
                            logger.info(f"📧 Marked reply email {email_id} as requiring action")
                        
                        logger.info(
                            f"Email analysis for {email_id}: "
                            f"category={analysis.get('category')}, "
                            f"requires_action={analysis.get('requires_action')}, "
                            f"action_type={analysis.get('action_type')}, "
                            f"urgency={analysis.get('urgency')}, "
                            f"is_reply_to_assistant={is_reply_to_assistant}"
                        )
                    except Exception as e:
                        logger.warning(f"Error analyzing email {email_id}: {e}")
                        analysis = None
                        # If analysis fails but it's a reply, still mark as requiring action
                        if is_reply_to_assistant:
                            analysis = {
                                "category": "direct",
                                "requires_action": True,
                                "action_type": "reply",
                                "action_summary": "Risposta a email inviata dall'assistente",
                                "urgency": "medium",
                                "is_reply_to_assistant": True,
                            }
                
                # Process action if analysis indicates action is required
                session_id = None
                if self.email_action_processor and analysis and analysis.get("requires_action"):
                    try:
                        # Use integration.user_id if available, otherwise skip session creation
                        # (notifications can still be created without user_id)
                        if integration.user_id:
                            logger.info(f"🔄 Processing email action for {email_id}: requires_action=True, urgency={analysis.get('urgency')}, action_type={analysis.get('action_type')}")
                            session_id = await self.email_action_processor.process_email_action(
                                email=msg,
                                analysis=analysis,
                                tenant_id=integration.tenant_id,
                                user_id=integration.user_id,
                            )
                            if session_id:
                                logger.info(f"✅ Created automatic session {session_id} for email {email_id}")
                            else:
                                logger.warning(f"⚠️  No session created for email {email_id} (process_email_action returned None)")
                        else:
                            logger.warning(f"⚠️  Cannot create session for email {email_id}: integration {integration.id} has no user_id. Notification will still be created.")
                            logger.warning(f"   This integration should be recreated with proper user_id. Check OAuth callback logs.")
                    except Exception as e:
                        logger.error(f"❌ Error processing email action for {email_id}: {e}", exc_info=True)
                
                # Determina priorità basata su analisi o fallback a metodo tradizionale
                if analysis:
                    priority = analysis.get("urgency", "medium")
                else:
                    priority = self._determine_email_priority(msg)
                
                # Crea notifica (controlla duplicati basati su email_id)
                # IMPORTANTE: Aggiungi user_id al content per filtrare le notifiche per utente
                logger.info(f"📧 Creating notification for email {email_id} (integration: {integration.id}, user_id: {integration.user_id})")
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
                        "user_id": str(integration.user_id) if integration.user_id else None,  # Aggiungi user_id per filtrare
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
                    logger.info(f"⏭️  Skipping duplicate notification for email {email_id} (integration: {integration.id})")
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

