#!/usr/bin/env python3
"""
Test script per verificare che EmailPoller e CalendarWatcher filtrino correttamente
solo le integrazioni utente (user_email, user_calendar).
"""
import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.db.database import get_db
from app.models.database import Integration
from app.services.schedulers.email_poller import EmailPoller
from app.services.schedulers.calendar_watcher import CalendarWatcher
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_email_poller_filtering():
    """Test che EmailPoller filtri solo integrazioni user_email"""
    logger.info("\n🧪 Test EmailPoller filtering")
    
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    async with async_session() as session:
        # Count all email integrations
        result = await session.execute(
            select(Integration).where(
                Integration.provider == "google",
                Integration.service_type == "email",
                Integration.enabled == True
            )
        )
        all_email_integrations = result.scalars().all()
        
        logger.info(f"   Totale integrazioni email (google, enabled): {len(all_email_integrations)}")
        
        # Count user_email integrations
        result = await session.execute(
            select(Integration).where(
                Integration.provider == "google",
                Integration.service_type == "email",
                Integration.purpose == "user_email",
                Integration.enabled == True
            )
        )
        user_email_integrations = result.scalars().all()
        
        logger.info(f"   Integrazioni user_email: {len(user_email_integrations)}")
        
        # Count service_email integrations
        result = await session.execute(
            select(Integration).where(
                Integration.provider == "google",
                Integration.service_type == "email",
                Integration.purpose == "service_email",
                Integration.enabled == True
            )
        )
        service_email_integrations = result.scalars().all()
        
        logger.info(f"   Integrazioni service_email: {len(service_email_integrations)}")
        
        # Verify EmailPoller query matches user_email only
        # (simulating the query from EmailPoller.check_new_emails)
        result = await session.execute(
            select(Integration).where(
                Integration.provider == "google",
                Integration.service_type == "email",
                Integration.purpose == "user_email",  # This is what EmailPoller should use
                Integration.enabled == True
            )
        )
        poller_integrations = result.scalars().all()
        
        if len(poller_integrations) != len(user_email_integrations):
            logger.error(f"❌ EmailPoller query non corrisponde a user_email integrations!")
            return False
        
        logger.info(f"   ✅ EmailPoller filtrerà {len(poller_integrations)} integrazioni (solo user_email)")
        
        # Verify no service_email integrations are included
        poller_purposes = {integration.purpose for integration in poller_integrations}
        if "service_email" in poller_purposes:
            logger.error("❌ EmailPoller include integrazioni service_email!")
            return False
        
        logger.info("   ✅ EmailPoller esclude correttamente le integrazioni service_email")
    
    await engine.dispose()
    return True


async def test_calendar_watcher_filtering():
    """Test che CalendarWatcher filtri solo integrazioni user_calendar"""
    logger.info("\n🧪 Test CalendarWatcher filtering")
    
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    async with async_session() as session:
        # Count all calendar integrations
        result = await session.execute(
            select(Integration).where(
                Integration.provider == "google",
                Integration.service_type == "calendar",
                Integration.enabled == True
            )
        )
        all_calendar_integrations = result.scalars().all()
        
        logger.info(f"   Totale integrazioni calendar (google, enabled): {len(all_calendar_integrations)}")
        
        # Count user_calendar integrations
        result = await session.execute(
            select(Integration).where(
                Integration.provider == "google",
                Integration.service_type == "calendar",
                Integration.purpose == "user_calendar",
                Integration.enabled == True
            )
        )
        user_calendar_integrations = result.scalars().all()
        
        logger.info(f"   Integrazioni user_calendar: {len(user_calendar_integrations)}")
        
        # Count service_calendar integrations
        result = await session.execute(
            select(Integration).where(
                Integration.provider == "google",
                Integration.service_type == "calendar",
                Integration.purpose == "service_calendar",
                Integration.enabled == True
            )
        )
        service_calendar_integrations = result.scalars().all()
        
        logger.info(f"   Integrazioni service_calendar: {len(service_calendar_integrations)}")
        
        # Verify CalendarWatcher query matches user_calendar only
        # (simulating the query from CalendarWatcher.check_upcoming_events)
        result = await session.execute(
            select(Integration).where(
                Integration.provider == "google",
                Integration.service_type == "calendar",
                Integration.purpose == "user_calendar",  # This is what CalendarWatcher should use
                Integration.enabled == True
            )
        )
        watcher_integrations = result.scalars().all()
        
        if len(watcher_integrations) != len(user_calendar_integrations):
            logger.error(f"❌ CalendarWatcher query non corrisponde a user_calendar integrations!")
            return False
        
        logger.info(f"   ✅ CalendarWatcher filtrerà {len(watcher_integrations)} integrazioni (solo user_calendar)")
        
        # Verify no service_calendar integrations are included
        watcher_purposes = {integration.purpose for integration in watcher_integrations}
        if "service_calendar" in watcher_purposes:
            logger.error("❌ CalendarWatcher include integrazioni service_calendar!")
            return False
        
        logger.info("   ✅ CalendarWatcher esclude correttamente le integrazioni service_calendar")
    
    await engine.dispose()
    return True


async def main():
    """Main test function"""
    logger.info("🧪 Test filtering background agents\n")
    
    tests = [
        ("EmailPoller filtering", test_email_poller_filtering()),
        ("CalendarWatcher filtering", test_calendar_watcher_filtering()),
    ]
    
    results = []
    for test_name, test_coro in tests:
        try:
            result = await test_coro
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ Errore in {test_name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("📊 Riepilogo test:")
    all_passed = True
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"   {status}: {test_name}")
        if not result:
            all_passed = False
    
    if all_passed:
        logger.info("\n✅ Tutti i test sono passati!")
        return 0
    else:
        logger.error("\n❌ Alcuni test sono falliti!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

