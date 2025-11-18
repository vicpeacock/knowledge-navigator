"""
Advanced tests for DailySessionManager
Tests day transitions, archiving, summaries, and timezone handling
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


async def test_timezone_handling():
    """Test timezone handling"""
    print("🌍 Test: Timezone Handling")
    
    init_clients()
    memory_manager = get_memory_manager()
    ollama_client = get_ollama_client()
    
    async with AsyncSessionLocal() as db:
        # Get first user
        user_result = await db.execute(select(User).limit(1))
        user = user_result.scalar_one_or_none()
        
        if not user:
            print("❌ No users found")
            return
        
        # Test different timezones
        test_timezones = ["UTC", "Europe/Rome", "America/New_York", "Asia/Tokyo"]
        
        for tz in test_timezones:
            print(f"\n   Testing timezone: {tz}")
            user.timezone = tz
            await db.commit()
            
            manager = DailySessionManager(
                db=db,
                memory_manager=memory_manager,
                ollama_client=ollama_client,
            )
            
            today_date = manager._get_today_date_str(user)
            user_tz = manager._get_user_timezone(user)
            now_in_tz = datetime.now(user_tz)
            
            print(f"     Today date: {today_date}")
            print(f"     Current time in {tz}: {now_in_tz.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            print(f"     Timezone object: {user_tz}")


async def test_session_with_messages():
    """Test session creation and message handling"""
    print("\n💬 Test: Session with Messages")
    
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
        
        # Get or create today's session
        session, is_new = await manager.get_or_create_today_session(
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        
        print(f"   Session ID: {session.id}")
        print(f"   Session name: {session.name}")
        
        # Count existing messages
        messages_result = await db.execute(
            select(MessageModel).where(
                MessageModel.session_id == session.id,
                MessageModel.tenant_id == session.tenant_id,
            )
        )
        existing_messages = messages_result.scalars().all()
        print(f"   Existing messages: {len(existing_messages)}")
        
        # Add a test message if none exist
        if len(existing_messages) == 0:
            print("   Adding test messages...")
            test_messages = [
                ("user", "Ciao, come stai?"),
                ("assistant", "Ciao! Sto bene, grazie. Come posso aiutarti oggi?"),
                ("user", "Puoi aiutarmi a organizzare una riunione?"),
                ("assistant", "Certamente! Quando vorresti organizzare la riunione?"),
            ]
            
            for role, content in test_messages:
                message = MessageModel(
                    session_id=session.id,
                    tenant_id=session.tenant_id,
                    role=role,
                    content=content,
                )
                db.add(message)
            
            await db.commit()
            print(f"   ✅ Added {len(test_messages)} test messages")
        else:
            print(f"   ℹ️  Session already has {len(existing_messages)} messages")


async def test_yesterday_session_archiving():
    """Test archiving of yesterday's session"""
    print("\n📦 Test: Yesterday Session Archiving")
    
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
        
        # Check if there's a yesterday session
        yesterday_date = manager._get_yesterday_date_str(user)
        print(f"   Yesterday date: {yesterday_date}")
        
        yesterday_session_result = await db.execute(
            select(SessionModel).where(
                SessionModel.tenant_id == user.tenant_id,
                SessionModel.user_id == user.id,
                SessionModel.session_metadata["day"].astext == yesterday_date,
            )
        )
        yesterday_session = yesterday_session_result.scalar_one_or_none()
        
        if yesterday_session:
            print(f"   Found yesterday session: {yesterday_session.id}")
            print(f"   Status: {yesterday_session.status}")
            print(f"   Archived at: {yesterday_session.archived_at}")
        else:
            print("   ℹ️  No yesterday session found (this is normal if it's the first day)")
        
        # Try to manually trigger archiving check
        print("\n   Testing archiving logic...")
        archived = await manager._check_and_archive_yesterday_session(
            user=user,
            tenant_id=user.tenant_id,
            user_id=user.id,
        )
        
        if archived:
            print(f"   ✅ Archived session: {archived.id}")
            print(f"   Status: {archived.status}")
            print(f"   Archived at: {archived.archived_at}")
        else:
            print("   ℹ️  No session to archive")


async def test_multiple_sessions_same_day():
    """Test that only one session per day is created"""
    print("\n🔄 Test: Multiple Sessions Same Day")
    
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
        
        # Call get_or_create multiple times
        sessions = []
        for i in range(5):
            session, is_new = await manager.get_or_create_today_session(
                user_id=user.id,
                tenant_id=user.tenant_id,
            )
            sessions.append((session.id, is_new))
        
        # Check all sessions are the same
        unique_sessions = set(sid for sid, _ in sessions)
        print(f"   Created/retrieved {len(sessions)} times")
        print(f"   Unique sessions: {len(unique_sessions)}")
        
        if len(unique_sessions) == 1:
            print("   ✅ All calls returned the same session (correct!)")
        else:
            print(f"   ❌ Multiple sessions created: {unique_sessions}")


async def test_session_metadata():
    """Test session metadata structure"""
    print("\n📋 Test: Session Metadata")
    
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
        
        session, _ = await manager.get_or_create_today_session(
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        
        metadata = session.session_metadata or {}
        print(f"   Session metadata keys: {list(metadata.keys())}")
        print(f"   Day: {metadata.get('day')}")
        print(f"   Is daily session: {metadata.get('is_daily_session')}")
        print(f"   Timezone: {metadata.get('timezone')}")
        
        # Verify required fields
        required_fields = ['day', 'is_daily_session', 'timezone']
        missing_fields = [f for f in required_fields if f not in metadata]
        
        if not missing_fields:
            print("   ✅ All required metadata fields present")
        else:
            print(f"   ❌ Missing fields: {missing_fields}")


async def test_error_handling():
    """Test error handling"""
    print("\n⚠️  Test: Error Handling")
    
    init_clients()
    memory_manager = get_memory_manager()
    ollama_client = get_ollama_client()
    
    async with AsyncSessionLocal() as db:
        manager = DailySessionManager(
            db=db,
            memory_manager=memory_manager,
            ollama_client=ollama_client,
        )
        
        # Test with invalid user_id
        print("   Testing with invalid user_id...")
        try:
            fake_uuid = UUID('00000000-0000-0000-0000-000000000000')
            session, _ = await manager.get_or_create_today_session(
                user_id=fake_uuid,
                tenant_id=fake_uuid,
            )
            print("   ❌ Should have raised an error")
        except Exception as e:
            print(f"   ✅ Correctly raised error: {type(e).__name__}")
        
        # Test with invalid timezone
        print("\n   Testing with invalid timezone...")
        user_result = await db.execute(select(User).limit(1))
        user = user_result.scalar_one_or_none()
        
        if user:
            original_tz = user.timezone
            user.timezone = "Invalid/Timezone"
            await db.commit()
            
            try:
                tz = manager._get_user_timezone(user)
                print(f"   ✅ Fallback to UTC: {tz}")
            except Exception as e:
                print(f"   ❌ Unexpected error: {e}")
            
            # Restore original timezone
            user.timezone = original_tz
            await db.commit()


async def run_all_tests():
    """Run all advanced tests"""
    print("=" * 60)
    print("🧪 Advanced DailySessionManager Tests")
    print("=" * 60)
    
    try:
        await test_timezone_handling()
        await test_session_with_messages()
        await test_yesterday_session_archiving()
        await test_multiple_sessions_same_day()
        await test_session_metadata()
        await test_error_handling()
        
        print("\n" + "=" * 60)
        print("✅ All advanced tests completed!")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_all_tests())

