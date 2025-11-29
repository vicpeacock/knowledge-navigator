"""
Event Monitor Service - Orchestrates proactive event monitoring
"""
import logging
import asyncio
from typing import Optional
from datetime import datetime, UTC

from app.services.schedulers.email_poller import EmailPoller
from app.services.schedulers.calendar_watcher import CalendarWatcher
from app.services.agent_activity_stream import AgentActivityStream
from app.core.config import settings
from app.db.database import get_db

logger = logging.getLogger(__name__)


class EventMonitor:
    """
    Main service for monitoring external events (email, calendar, etc.)
    and creating proactive notifications.
    """
    
    def __init__(self, agent_activity_stream: Optional[AgentActivityStream] = None):
        self._running = False
        self._poll_interval_seconds = settings.event_monitor_poll_interval_seconds
        self._agent_activity_stream = agent_activity_stream
    
    async def start(self):
        """Start the event monitor in background"""
        if self._running:
            logger.warning("EventMonitor already running")
            return
        
        self._running = True
        logger.info("🚀 Starting EventMonitor service")
        
        # Avvia loop in background
        task = asyncio.create_task(self._monitor_loop())
        logger.info(f"✅ EventMonitor loop task created: {task}")
        
        # Log dopo un breve delay per verificare che il task sia in esecuzione
        async def check_task():
            await asyncio.sleep(2)
            if task.done():
                logger.error(f"❌ EventMonitor loop task completed unexpectedly: {task.exception()}")
            else:
                logger.info(f"✅ EventMonitor loop task is running")
        
        asyncio.create_task(check_task())
    
    async def stop(self):
        """Stop the event monitor"""
        self._running = False
        logger.info("🛑 Stopping EventMonitor service")
    
    async def _monitor_loop(self):
        """Main monitoring loop"""
        logger.info(f"🔄 EventMonitor loop started (poll_interval={self._poll_interval_seconds}s)")
        iteration = 0
        while self._running:
            iteration += 1
            try:
                logger.info(f"🔄 EventMonitor loop iteration {iteration} - checking events...")
                await self._check_all_events()
                logger.info(f"✅ EventMonitor loop iteration {iteration} completed")
            except Exception as e:
                logger.error(f"❌ Error in EventMonitor loop iteration {iteration}: {e}", exc_info=True)
            
            # Attendi prima del prossimo check
            logger.debug(f"⏳ EventMonitor waiting {self._poll_interval_seconds}s before next check...")
            await asyncio.sleep(self._poll_interval_seconds)
        
        logger.info("🛑 EventMonitor loop stopped")
    
    async def _check_all_events(self):
        """Check all event sources"""
        logger.info("🔍 Checking all event sources...")
        
        # Pubblica evento telemetria "started"
        self._publish_activity("started", "Checking for new events")
        
        # Crea una nuova sessione database per questo check
        async for db in get_db():
            try:
                # Crea poller/watcher con questa sessione
                email_poller = EmailPoller(db) if settings.email_poller_enabled else None
                calendar_watcher = CalendarWatcher(db) if settings.calendar_watcher_enabled else None
                
                # Check emails
                if email_poller:
                    try:
                        self._publish_activity("started", "Checking Gmail integrations", extra={"type": "email"})
                        email_events = await email_poller.check_new_emails()
                        if email_events:
                            logger.info(f"📧 Found {len(email_events)} new email events")
                            self._publish_activity(
                                "completed",
                                f"Found {len(email_events)} new email(s)",
                                extra={"type": "email", "count": len(email_events)}
                            )
                        else:
                            self._publish_activity("completed", "No new emails", extra={"type": "email"})
                    except Exception as e:
                        logger.error(f"Error checking emails: {e}", exc_info=True)
                        self._publish_activity("error", f"Email check failed: {str(e)}", extra={"type": "email"})
                
                # Check calendar
                if calendar_watcher:
                    try:
                        self._publish_activity("started", "Checking Calendar integrations", extra={"type": "calendar"})
                        calendar_events = await calendar_watcher.check_upcoming_events()
                        if calendar_events:
                            logger.info(f"📅 Found {len(calendar_events)} upcoming calendar events")
                            self._publish_activity(
                                "completed",
                                f"Found {len(calendar_events)} upcoming event(s)",
                                extra={"type": "calendar", "count": len(calendar_events)}
                            )
                        else:
                            self._publish_activity("completed", "No upcoming events", extra={"type": "calendar"})
                    except Exception as e:
                        logger.error(f"Error checking calendar: {e}", exc_info=True)
                        self._publish_activity("error", f"Calendar check failed: {str(e)}", extra={"type": "calendar"})
                
                # Pubblica evento telemetria "completed"
                self._publish_activity("completed", "Event check completed")
            finally:
                # La sessione viene chiusa automaticamente dal context manager
                break
    
    def _publish_activity(self, status: str, message: str, extra: Optional[dict] = None):
        """Publish telemetry event for proactivity system"""
        if not self._agent_activity_stream:
            logger.debug("⚠️  EventMonitor: No agent_activity_stream available, skipping telemetry")
            return
        
        event = {
            "agent_id": "event_monitor",
            "agent_name": "Event Monitor",
            "status": status,
            "timestamp": datetime.now(UTC),
            "message": message,
        }
        if extra:
            event.update(extra)
        
        try:
            # Check active sessions before publishing
            active_sessions = self._agent_activity_stream.get_active_sessions()
            logger.info(f"📡 EventMonitor publishing '{status}': {message} to {len(active_sessions)} active session(s): {active_sessions}")
            
            # Pubblica a tutte le sessioni attive (sistema di proattività è globale)
            self._agent_activity_stream.publish_to_all_active_sessions(event)
            
            if not active_sessions:
                # Log at DEBUG level to reduce log noise (no active sessions is normal when users are offline)
                logger.debug("EventMonitor: No active sessions, event will not be delivered to frontend")
        except Exception as e:
            logger.error(f"❌ Unable to publish event monitor telemetry: {e}", exc_info=True)
    
    async def check_once(self):
        """Run a single check (useful for testing or manual triggers)"""
        await self._check_all_events()

