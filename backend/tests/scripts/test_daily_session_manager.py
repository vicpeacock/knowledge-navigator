"""
Test script for DailySessionManager
"""
import asyncio
import sys
import os
from datetime import datetime
from uuid import UUID

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.db.database import AsyncSessionLocal
from app.models.database import User, Session as SessionModel
from app.services.daily_session_manager import DailySessionManager
from app.core.dependencies import init_clients, get_memory_manager, get_ollama_client
from sqlalchemy import select


async def test_daily_session_manager():
    """Test DailySessionManager functionality"""
    print("🧪 Testing DailySessionManager...")
    
    # Initialize clients
    init_clients()
    memory_manager = get_memory_manager()
    ollama_client = get_ollama_client()
    
    async with AsyncSessionLocal() as db:
        # Get first user (or create test user)
        user_result = await db.execute(
            select(User).limit(1)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            print("❌ No users found in database. Please create a user first.")
            return
        
        print(f"✅ Found user: {user.email} (ID: {user.id})")
        print(f"   Timezone: {user.timezone or 'UTC (default)'}")
        print(f"   Inactivity timeout: {user.inactivity_timeout_minutes or 30} minutes")
        
        # Create DailySessionManager
        manager = DailySessionManager(
            db=db,
            memory_manager=memory_manager,
            ollama_client=ollama_client,
        )
        
        # Test 1: Get or create today's session
        print("\n📅 Test 1: Get or create today's session")
        session, is_new = await manager.get_or_create_today_session(
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        print(f"   Session ID: {session.id}")
        print(f"   Name: {session.name}")
        print(f"   Is new: {is_new}")
        print(f"   Day in metadata: {session.session_metadata.get('day')}")
        print(f"   Is daily session: {session.session_metadata.get('is_daily_session')}")
        
        # Test 2: Get again (should return same session)
        print("\n📅 Test 2: Get same session again")
        session2, is_new2 = await manager.get_or_create_today_session(
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        print(f"   Session ID: {session2.id}")
        print(f"   Is new: {is_new2}")
        print(f"   Same session: {session.id == session2.id}")
        
        # Test 3: Check day transition (should return False since same day)
        print("\n📅 Test 3: Check day transition")
        transition, new_session = await manager.check_day_transition(
            user_id=user.id,
            tenant_id=user.tenant_id,
            current_session_id=session.id,
        )
        print(f"   Day transition detected: {transition}")
        print(f"   New session: {new_session}")
        
        # Test 4: List all sessions for user
        print("\n📅 Test 4: List all sessions for user")
        sessions_result = await db.execute(
            select(SessionModel).where(
                SessionModel.user_id == user.id,
                SessionModel.tenant_id == user.tenant_id,
            ).order_by(SessionModel.created_at.desc()).limit(5)
        )
        sessions = sessions_result.scalars().all()
        print(f"   Found {len(sessions)} sessions:")
        for s in sessions:
            day = s.session_metadata.get('day', 'N/A') if s.session_metadata else 'N/A'
            is_daily = s.session_metadata.get('is_daily_session', False) if s.session_metadata else False
            session_id_str = str(s.id)[:8] if s.id else 'N/A'
            print(f"     - {s.name} (ID: {session_id_str}..., Status: {s.status}, Day: {day}, Daily: {is_daily})")
        
        print("\n✅ All tests completed!")


if __name__ == "__main__":
    asyncio.run(test_daily_session_manager())

