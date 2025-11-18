"""
Test day transition simulation
This test simulates what happens when a day changes
"""
import asyncio
import sys
import os
from datetime import datetime, timedelta
from uuid import UUID

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.db.database import AsyncSessionLocal
from app.models.database import User, Session as SessionModel, Message as MessageModel
from app.services.daily_session_manager import DailySessionManager
from app.core.dependencies import init_clients, get_memory_manager, get_ollama_client
from sqlalchemy import select
from zoneinfo import ZoneInfo


async def simulate_day_transition():
    """Simulate a day transition by creating a session for yesterday and today"""
    print("🔄 Test: Simulating Day Transition")
    
    init_clients()
    memory_manager = get_memory_manager()
    ollama_client = get_ollama_client()
    
    async with AsyncSessionLocal() as db:
        user_result = await db.execute(select(User).limit(1))
        user = user_result.scalar_one_or_none()
        
        if not user:
            print("❌ No users found")
            return
        
        manager = DailySessionManager(
            db=db,
            memory_manager=memory_manager,
            ollama_client=ollama_client,
        )
        
        # Get today's date
        today_date = manager._get_today_date_str(user)
        yesterday_date = manager._get_yesterday_date_str(user)
        
        print(f"   Today: {today_date}")
        print(f"   Yesterday: {yesterday_date}")
        
        # Create a session for yesterday manually (to simulate old session)
        print("\n   1. Creating yesterday session manually...")
        yesterday_session = SessionModel(
            tenant_id=user.tenant_id,
            user_id=user.id,
            name=f"Sessione {yesterday_date}",
            title=f"Sessione {yesterday_date}",
            description=f"Test session for {yesterday_date}",
            status="active",
            session_metadata={
                "day": yesterday_date,
                "is_daily_session": True,
                "timezone": user.timezone or "UTC",
            },
        )
        db.add(yesterday_session)
        await db.commit()  # Commit session first to get ID
        await db.refresh(yesterday_session)
        
        # Add some test messages to yesterday session
        test_messages = [
            ("user", "Buongiorno! Oggi devo fare molte cose."),
            ("assistant", "Buongiorno! Sono qui per aiutarti. Cosa devi fare?"),
            ("user", "Devo organizzare una riunione e rispondere a delle email."),
            ("assistant", "Perfetto! Posso aiutarti con entrambe le cose. Iniziamo con la riunione?"),
        ]
        
        for role, content in test_messages:
            message = MessageModel(
                session_id=yesterday_session.id,
                tenant_id=user.tenant_id,
                role=role,
                content=content,
            )
            db.add(message)
        
        await db.commit()  # Commit messages
        
        print(f"   ✅ Created yesterday session: {yesterday_session.id}")
        print(f"   ✅ Added {len(test_messages)} messages")
        
        # Now get today's session - this should trigger archiving of yesterday
        print("\n   2. Getting today's session (should archive yesterday)...")
        today_session, is_new = await manager.get_or_create_today_session(
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        
        print(f"   Today session ID: {today_session.id}")
        print(f"   Is new: {is_new}")
        
        # Check if yesterday session was archived
        await db.refresh(yesterday_session)
        print(f"\n   3. Checking yesterday session status...")
        print(f"   Yesterday session status: {yesterday_session.status}")
        print(f"   Archived at: {yesterday_session.archived_at}")
        
        if yesterday_session.status == "archived":
            print("   ✅ Yesterday session was correctly archived!")
        else:
            print("   ⚠️  Yesterday session was not archived (might be same day?)")
        
        # Check if summary was generated
        metadata = yesterday_session.session_metadata or {}
        has_summary = "daily_summary" in metadata
        
        print(f"\n   4. Checking for daily summary...")
        if has_summary:
            summary = metadata.get("daily_summary", "")
            print(f"   ✅ Summary generated: {len(summary)} characters")
            print(f"   Preview: {summary[:200]}...")
        else:
            print("   ℹ️  No summary generated (Ollama might not be available or session had no messages)")
        
        # Verify today's session is different
        print(f"\n   5. Verifying sessions are different...")
        if today_session.id != yesterday_session.id:
            print("   ✅ Today and yesterday sessions are different (correct!)")
        else:
            print("   ⚠️  Sessions are the same (might be same day?)")


async def test_concurrent_access():
    """Test concurrent access to get_or_create_today_session"""
    print("\n🔀 Test: Concurrent Access")
    
    init_clients()
    memory_manager = get_memory_manager()
    ollama_client = get_ollama_client()
    
    async with AsyncSessionLocal() as db:
        user_result = await db.execute(select(User).limit(1))
        user = user_result.scalar_one_or_none()
        
        if not user:
            print("❌ No users found")
            return
        
        async def get_session():
            async with AsyncSessionLocal() as session_db:
                manager = DailySessionManager(
                    db=session_db,
                    memory_manager=memory_manager,
                    ollama_client=ollama_client,
                )
                session, is_new = await manager.get_or_create_today_session(
                    user_id=user.id,
                    tenant_id=user.tenant_id,
                )
                return session.id
        
        # Call concurrently
        print("   Making 10 concurrent calls...")
        tasks = [get_session() for _ in range(10)]
        session_ids = await asyncio.gather(*tasks)
        
        unique_sessions = set(session_ids)
        print(f"   Got {len(session_ids)} results")
        print(f"   Unique sessions: {len(unique_sessions)}")
        
        if len(unique_sessions) == 1:
            print("   ✅ All concurrent calls returned the same session (correct!)")
        else:
            print(f"   ⚠️  Multiple sessions created: {unique_sessions}")


async def run_all_tests():
    """Run all day transition tests"""
    print("=" * 60)
    print("🔄 Day Transition Tests")
    print("=" * 60)
    
    try:
        await simulate_day_transition()
        await test_concurrent_access()
        
        print("\n" + "=" * 60)
        print("✅ All day transition tests completed!")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_all_tests())

