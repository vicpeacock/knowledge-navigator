"""
Integration tests for daily session management
Tests the integration of DailySessionManager with EmailActionProcessor and chat endpoint
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
from app.services.email_action_processor import EmailActionProcessor
from app.core.dependencies import init_clients, get_memory_manager, get_ollama_client
from sqlalchemy import select


async def test_email_added_to_daily_session():
    """Test that emails are added to daily session instead of creating ad-hoc sessions"""
    print("📧 Test: Email Added to Daily Session")
    
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
        
        # Get or create today's session
        daily_manager = DailySessionManager(
            db=db,
            memory_manager=memory_manager,
            ollama_client=ollama_client,
        )
        today_session, _ = await daily_manager.get_or_create_today_session(
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        
        print(f"   Today's session: {today_session.id}")
        
        # Count messages before
        messages_before = await db.execute(
            select(MessageModel).where(
                MessageModel.session_id == today_session.id,
                MessageModel.tenant_id == user.tenant_id,
            )
        )
        count_before = len(messages_before.scalars().all())
        print(f"   Messages before: {count_before}")
        
        # Process a test email
        email_processor = EmailActionProcessor(
            db=db,
            memory_manager=memory_manager,
            ollama_client=ollama_client,
        )
        
        test_email = {
            "id": "test_email_123",
            "subject": "Test Email Subject",
            "from": "test@example.com",
            "snippet": "This is a test email snippet",
            "date": datetime.now().isoformat(),
        }
        
        test_analysis = {
            "requires_action": True,
            "action_type": "reply",
            "urgency": "medium",
            "action_summary": "Test action required",
        }
        
        session_id = await email_processor.process_email_action(
            email=test_email,
            analysis=test_analysis,
            tenant_id=user.tenant_id,
            user_id=user.id,
        )
        
        if session_id:
            print(f"   ✅ Email processed, session_id: {session_id}")
            print(f"   Same as today's session: {session_id == today_session.id}")
            
            # Count messages after
            messages_after = await db.execute(
                select(MessageModel).where(
                    MessageModel.session_id == session_id,
                    MessageModel.tenant_id == user.tenant_id,
                )
            )
            count_after = len(messages_after.scalars().all())
            print(f"   Messages after: {count_after}")
            print(f"   New messages added: {count_after - count_before}")
            
            if session_id == today_session.id:
                print("   ✅ Email correctly added to today's daily session")
            else:
                print("   ❌ Email added to different session")
        else:
            print("   ⚠️  Email processing returned None (might be deduplicated)")


async def test_email_deduplication():
    """Test that same email is not processed twice"""
    print("\n🔄 Test: Email Deduplication")
    
    init_clients()
    memory_manager = get_memory_manager()
    ollama_client = get_ollama_client()
    
    async with AsyncSessionLocal() as db:
        user_result = await db.execute(select(User).limit(1))
        user = user_result.scalar_one_or_none()
        
        if not user:
            print("❌ No users found")
            return
        
        email_processor = EmailActionProcessor(
            db=db,
            memory_manager=memory_manager,
            ollama_client=ollama_client,
        )
        
        test_email = {
            "id": "dedup_test_email_456",
            "subject": "Deduplication Test",
            "from": "test@example.com",
            "snippet": "Test for deduplication",
            "date": datetime.now().isoformat(),
        }
        
        test_analysis = {
            "requires_action": True,
            "action_type": "reply",
            "urgency": "medium",
            "action_summary": "Test action",
        }
        
        # Process first time
        session_id_1 = await email_processor.process_email_action(
            email=test_email,
            analysis=test_analysis,
            tenant_id=user.tenant_id,
            user_id=user.id,
        )
        
        print(f"   First processing: session_id = {session_id_1}")
        
        # Process second time (should be deduplicated)
        session_id_2 = await email_processor.process_email_action(
            email=test_email,
            analysis=test_analysis,
            tenant_id=user.tenant_id,
            user_id=user.id,
        )
        
        print(f"   Second processing: session_id = {session_id_2}")
        
        if session_id_1 and not session_id_2:
            print("   ✅ Email correctly deduplicated on second processing")
        elif session_id_1 == session_id_2:
            print("   ⚠️  Email processed twice (deduplication might not be working)")
        else:
            print("   ❌ Unexpected behavior")


async def test_session_metadata_tracking():
    """Test that processed emails are tracked in session metadata"""
    print("\n📋 Test: Session Metadata Tracking")
    
    init_clients()
    memory_manager = get_memory_manager()
    ollama_client = get_ollama_client()
    
    async with AsyncSessionLocal() as db:
        user_result = await db.execute(select(User).limit(1))
        user = user_result.scalar_one_or_none()
        
        if not user:
            print("❌ No users found")
            return
        
        daily_manager = DailySessionManager(
            db=db,
            memory_manager=memory_manager,
            ollama_client=ollama_client,
        )
        session, _ = await daily_manager.get_or_create_today_session(
            user_id=user.id,
            tenant_id=user.tenant_id,
        )
        
        metadata = session.session_metadata or {}
        print(f"   Session metadata keys: {list(metadata.keys())}")
        
        processed_emails = metadata.get("processed_emails", [])
        print(f"   Processed emails count: {len(processed_emails)}")
        
        if processed_emails:
            print(f"   Sample processed email: {processed_emails[0]}")
            print("   ✅ Processed emails are tracked in metadata")
        else:
            print("   ℹ️  No processed emails yet (this is normal if no emails were processed)")


async def test_multiple_emails_same_session():
    """Test that multiple emails are added to the same daily session"""
    print("\n📬 Test: Multiple Emails Same Session")
    
    init_clients()
    memory_manager = get_memory_manager()
    ollama_client = get_ollama_client()
    
    async with AsyncSessionLocal() as db:
        user_result = await db.execute(select(User).limit(1))
        user = user_result.scalar_one_or_none()
        
        if not user:
            print("❌ No users found")
            return
        
        email_processor = EmailActionProcessor(
            db=db,
            memory_manager=memory_manager,
            ollama_client=ollama_client,
        )
        
        test_emails = [
            {
                "id": f"multi_email_{i}",
                "subject": f"Test Email {i}",
                "from": f"sender{i}@example.com",
                "snippet": f"Content of email {i}",
                "date": datetime.now().isoformat(),
            }
            for i in range(3)
        ]
        
        test_analysis = {
            "requires_action": True,
            "action_type": "reply",
            "urgency": "medium",
            "action_summary": "Test action",
        }
        
        session_ids = []
        for email in test_emails:
            session_id = await email_processor.process_email_action(
                email=email,
                analysis=test_analysis,
                tenant_id=user.tenant_id,
                user_id=user.id,
            )
            if session_id:
                session_ids.append(session_id)
        
        unique_sessions = set(session_ids)
        print(f"   Processed {len(test_emails)} emails")
        print(f"   Unique sessions: {len(unique_sessions)}")
        print(f"   Session IDs: {unique_sessions}")
        
        if len(unique_sessions) == 1:
            print("   ✅ All emails added to same daily session")
        else:
            print(f"   ⚠️  Emails added to {len(unique_sessions)} different sessions")


async def run_all_tests():
    """Run all integration tests"""
    print("=" * 60)
    print("🧪 Daily Session Integration Tests")
    print("=" * 60)
    
    try:
        await test_email_added_to_daily_session()
        await test_email_deduplication()
        await test_session_metadata_tracking()
        await test_multiple_emails_same_session()
        
        print("\n" + "=" * 60)
        print("✅ All integration tests completed!")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_all_tests())

