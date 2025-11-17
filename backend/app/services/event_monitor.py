"""
Event Monitor Service - Orchestrates proactive event monitoring
"""
import logging
import asyncio
from typing import Optional
from datetime import datetime, timezone

from app.services.schedulers.email_poller import EmailPoller
from app.services.schedulers.calendar_watcher import CalendarWatcher
from app.core.config import settings
from app.db.database import get_db

logger = logging.getLogger(__name__)


class EventMonitor:
    """
    Main service for monitoring external events (email, calendar, etc.)
    and creating proactive notifications.
    """
    
    def __init__(self):
        self._running = False
        self._poll_interval_seconds = settings.event_monitor_poll_interval_seconds
    
    async def start(self):
        """Start the event monitor in background"""
        if self._running:
            logger.warning("EventMonitor already running")
            return
        
        self._running = True
        logger.info("🚀 Starting EventMonitor service")
        
        # Avvia loop in background
        asyncio.create_task(self._monitor_loop())
    
    async def stop(self):
        """Stop the event monitor"""
        self._running = False
        logger.info("🛑 Stopping EventMonitor service")
    
    async def _monitor_loop(self):
        """Main monitoring loop"""
        while self._running:
            try:
                await self._check_all_events()
            except Exception as e:
                logger.error(f"Error in EventMonitor loop: {e}", exc_info=True)
            
            # Attendi prima del prossimo check
            await asyncio.sleep(self._poll_interval_seconds)
    
    async def _check_all_events(self):
        """Check all event sources"""
        logger.debug("Checking all event sources...")
        
        # Crea una nuova sessione database per questo check
        async for db in get_db():
            try:
                # Crea poller/watcher con questa sessione
                email_poller = EmailPoller(db) if settings.email_poller_enabled else None
                calendar_watcher = CalendarWatcher(db) if settings.calendar_watcher_enabled else None
                
                # Check emails
                if email_poller:
                    try:
                        email_events = await email_poller.check_new_emails()
                        if email_events:
                            logger.info(f"📧 Found {len(email_events)} new email events")
                    except Exception as e:
                        logger.error(f"Error checking emails: {e}", exc_info=True)
                
                # Check calendar
                if calendar_watcher:
                    try:
                        calendar_events = await calendar_watcher.check_upcoming_events()
                        if calendar_events:
                            logger.info(f"📅 Found {len(calendar_events)} upcoming calendar events")
                    except Exception as e:
                        logger.error(f"Error checking calendar: {e}", exc_info=True)
            finally:
                # La sessione viene chiusa automaticamente dal context manager
                break
    
    async def check_once(self):
        """Run a single check (useful for testing or manual triggers)"""
        await self._check_all_events()

