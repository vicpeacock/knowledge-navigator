"""
Test day transition via API endpoint
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


async def test_day_transition_detection():
    """Test that day transition is correctly detected"""
    print("🔄 Test: Day Transition Detection")
    
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
        
        # Get today's session
        today_session, _ = await manager.get_or_create_today_session(
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        
        print(f"   Today's session: {today_session.id}")
        
        # Check transition with same session (should return False)
        transition, new_session = await manager.check_day_transition(
            user_id=user.id,
            tenant_id=user.tenant_id,
            current_session_id=today_session.id,
        )
        
        print(f"   Transition detected: {transition}")
        print(f"   New session: {new_session}")
        
        if not transition:
            print("   ✅ Correctly detected no transition (same day)")
        else:
            print("   ⚠️  False positive transition detected")
        
        # Check transition with non-existent session (should create today's session)
        fake_session_id = UUID('00000000-0000-0000-0000-000000000000')
        transition2, new_session2 = await manager.check_day_transition(
            user_id=user.id,
            tenant_id=user.tenant_id,
            current_session_id=fake_session_id,
        )
        
        print(f"\n   With fake session ID:")
        print(f"   Transition detected: {transition2}")
        print(f"   New session: {new_session2.id if new_session2 else None}")
        
        if transition2 and new_session2:
            print("   ✅ Correctly detected transition and created new session")
        else:
            print("   ⚠️  Transition not detected or session not created")


async def test_chat_response_structure():
    """Test that ChatResponse includes day_transition fields"""
    print("\n📋 Test: ChatResponse Structure")
    
    # Import ChatResponse schema
    from app.models.schemas import ChatResponse
    
    # Create a test response with day transition
    test_response = ChatResponse(
        response="",
        session_id=UUID('00000000-0000-0000-0000-000000000000'),
        memory_used={},
        tools_used=[],
        notifications_count=0,
        high_urgency_notifications=[],
        agent_activity=[],
        day_transition_pending=True,
        new_session_id="test-session-id",
    )
    
    print(f"   day_transition_pending: {test_response.day_transition_pending}")
    print(f"   new_session_id: {test_response.new_session_id}")
    
    if test_response.day_transition_pending and test_response.new_session_id:
        print("   ✅ ChatResponse correctly includes day transition fields")
    else:
        print("   ❌ ChatResponse missing day transition fields")


async def run_all_tests():
    """Run all API tests"""
    print("=" * 60)
    print("🧪 Day Transition API Tests")
    print("=" * 60)
    
    try:
        await test_day_transition_detection()
        await test_chat_response_structure()
        
        print("\n" + "=" * 60)
        print("✅ All API tests completed!")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_all_tests())

