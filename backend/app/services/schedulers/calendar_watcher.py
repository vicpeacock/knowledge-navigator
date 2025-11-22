"""
Calendar Watcher - Checks for upcoming calendar events and creates proactive notifications
"""
import logging
import json
import base64
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from cryptography.fernet import Fernet

from app.models.database import Integration
from app.services.calendar_service import CalendarService
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


class CalendarWatcher:
    """Watches calendar integrations for upcoming events and creates notifications"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.calendar_service = CalendarService()
        self.notification_service = NotificationService(db)
        # Reminder times: 15 minuti e 5 minuti prima
        self.reminder_minutes = [15, 5]
    
    async def check_upcoming_events(self) -> List[Dict[str, Any]]:
        """
        Check all Calendar integrations for upcoming events.
        Returns list of events created.
        """
        events_created = []
        
        # Get all active Google Calendar integrations
        result = await self.db.execute(
            select(Integration).where(
                Integration.provider == "google",
                Integration.service_type == "calendar",
                Integration.enabled == True
            )
        )
        integrations = result.scalars().all()
        
        if not integrations:
            logger.debug("No active Calendar integrations found")
            return events_created
        
        logger.info(f"Checking {len(integrations)} Calendar integrations for upcoming events")
        
        for integration in integrations:
            try:
                events = await self._check_integration_events(integration)
                events_created.extend(events)
            except Exception as e:
                logger.error(
                    f"Error checking calendar for integration {integration.id}: {e}",
                    exc_info=True
                )
                continue
        
        return events_created
    
    async def _check_integration_events(self, integration: Integration) -> List[Dict[str, Any]]:
        """Check upcoming events for a specific integration"""
        events_created = []
        
        # Check user preferences for calendar notifications (if integration has a user_id)
        if integration.user_id:
            from app.models.database import User
            user_result = await self.db.execute(
                select(User).where(User.id == integration.user_id)
            )
            user = user_result.scalar_one_or_none()
            if user:
                user_metadata = user.user_metadata or {}
                background_services = user_metadata.get("background_services", {})
                calendar_notifications_enabled = background_services.get("calendar_notifications_enabled", True)
                
                if not calendar_notifications_enabled:
                    logger.info(f"📅 Calendar notifications disabled for user {user.email} (integration {integration.id}) - skipping")
                    return events_created
            else:
                logger.warning(f"⚠️  User {integration.user_id} not found for integration {integration.id}")
        # For global integrations (user_id = NULL), check all users in tenant
        # For now, we'll create notifications for global integrations (backward compatibility)
        # TODO: Consider adding tenant-level preferences or checking all users
        
        # Setup calendar service per questa integrazione
        try:
            # Decrypt credentials
            credentials = _decrypt_credentials(
                integration.credentials_encrypted,
                settings.credentials_encryption_key
            )
            
            # Setup Google Calendar service
            await self.calendar_service.setup_google(
                credentials,
                integration_id=str(integration.id)
            )
        except ValueError as e:
            # Decryption error - credentials may be corrupted or key changed
            error_msg = str(e)
            if "decrypting credentials" in error_msg.lower():
                logger.error(
                    f"Error decrypting credentials for integration {integration.id}: {error_msg}. "
                    f"User needs to reconnect Calendar integration."
                )
            else:
                logger.error(f"Error setting up Calendar for integration {integration.id}: {error_msg}")
            return events_created
        except IntegrationAuthError as e:
            logger.warning(f"Integration {integration.id} auth failed: {e}")
            return events_created
        except Exception as e:
            logger.error(f"Error setting up Calendar for integration {integration.id}: {e}")
            return events_created
        
        # Get events nelle prossime 2 ore
        now = datetime.now(timezone.utc)
        end_time = now + timedelta(hours=2)
        
        try:
            calendar_events = await self.calendar_service.get_google_events(
                start_time=now,
                end_time=end_time,
                max_results=50,
                integration_id=str(integration.id)
            )
        except Exception as e:
            logger.error(f"Error fetching calendar events for integration {integration.id}: {e}")
            return events_created
        
        if not calendar_events:
            logger.debug(f"No upcoming events for integration {integration.id}")
            return events_created
        
        # Controlla ogni evento per vedere se è in prossimità di un reminder
        for event in calendar_events:
            try:
                # Parse event start time
                start_time = self._parse_event_start(event)
                if not start_time:
                    continue
                
                # Calcola tempo rimanente
                time_until_start = start_time - now
                
                # Controlla se siamo in prossimità di un reminder
                for reminder_minutes in self.reminder_minutes:
                    reminder_time = timedelta(minutes=reminder_minutes)
                    # Crea notifica se siamo tra reminder_time e reminder_time - 1 minuto
                    # (per evitare notifiche duplicate)
                    if timedelta(minutes=reminder_minutes - 1) < time_until_start <= reminder_time:
                        # Verifica se abbiamo già creato questa notifica
                        # (controlla se esiste già una notifica per questo evento con questo reminder)
                        event_id = event.get("id")
                        
                        # Crea notifica (controlla duplicati basati su event_id + reminder_minutes)
                        # Usa una chiave composita per evitare duplicati per lo stesso reminder
                        reminder_key = f"{event_id}_{reminder_minutes}"
                        priority = "high" if reminder_minutes <= 5 else "medium"
                        notification = await self.notification_service.create_notification(
                            type="calendar_event_starting",
                            urgency=priority,
                            content={
                                "event_id": event_id,
                                "summary": event.get("summary", "Untitled Event"),
                                "title": event.get("summary", "Untitled Event"),  # Alias per compatibilità
                                "start_time": start_time.isoformat(),
                                "end_time": event.get("end_time"),
                                "location": event.get("location"),
                                "reminder_minutes": reminder_minutes,
                                "reminder_key": reminder_key,  # Chiave per deduplicazione
                                "time_until_start_minutes": int(time_until_start.total_seconds() / 60),
                                "integration_id": str(integration.id),
                                "user_id": str(integration.user_id) if integration.user_id else None,  # Aggiungi user_id per filtrare
                            },
                            session_id=None,
                            tenant_id=integration.tenant_id,
                            check_duplicate={"key": "reminder_key", "value": reminder_key} if reminder_key else None,
                        )
                        
                        # Skip se notifica duplicata
                        if not notification:
                            logger.debug(f"Skipping duplicate notification for event {event_id} reminder {reminder_minutes}min")
                            continue
                        
                        events_created.append({
                            "type": "calendar_event_starting",
                            "priority": priority,
                            "notification_id": str(notification.id),
                            "event_title": event.get("summary"),
                            "reminder_minutes": reminder_minutes,
                        })
                        
                        logger.info(
                            f"Created notification for event '{event.get('summary')}' "
                            f"starting in {reminder_minutes} minutes"
                        )
                        break  # Solo un reminder per volta
            except Exception as e:
                logger.error(f"Error processing event {event.get('id')}: {e}")
                continue
        
        return events_created
    
    def _parse_event_start(self, event: Dict[str, Any]) -> Optional[datetime]:
        """Parse event start time from Google Calendar event format"""
        start = event.get("start")
        if not start:
            return None
        
        # Google Calendar può avere "dateTime" o "date"
        if "dateTime" in start:
            try:
                dt = datetime.fromisoformat(start["dateTime"].replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception as e:
                logger.warning(f"Error parsing dateTime: {e}")
                return None
        elif "date" in start:
            # All-day event
            try:
                dt = datetime.fromisoformat(start["date"])
                return dt.replace(tzinfo=timezone.utc)
            except Exception as e:
                logger.warning(f"Error parsing date: {e}")
                return None
        
        return None

