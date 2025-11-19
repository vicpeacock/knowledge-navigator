#!/usr/bin/env python3
"""
Script per migrare i messaggi dalla sessione di ieri a quella odierna
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from app.db.database import AsyncSessionLocal
from app.models.database import Session as SessionModel, Message as MessageModel, User


async def migrate_messages(user_email: str = "admin@example.com"):
    """Migrate messages from yesterday's session to today's session"""
    
    async with AsyncSessionLocal() as db:
        # Get user
        user_result = await db.execute(
            select(User).where(User.email == user_email)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            print(f"❌ Utente {user_email} non trovato")
            return
        
        # Get today's session
        from app.services.daily_session_manager import DailySessionManager
        daily_mgr = DailySessionManager(db)
        today_session, _ = await daily_mgr.get_or_create_today_session(
            user_id=user.id,
            tenant_id=user.tenant_id
        )
        
        print(f"✅ Sessione odierna: {today_session.id} ({today_session.name})")
        
        # Get yesterday's session
        yesterday_date = daily_mgr._get_yesterday_date_str(user)
        yesterday_session_result = await db.execute(
            select(SessionModel).where(
                SessionModel.tenant_id == user.tenant_id,
                SessionModel.user_id == user.id,
                SessionModel.session_metadata["day"].astext == yesterday_date,
            )
        )
        yesterday_session = yesterday_session_result.scalar_one_or_none()
        
        if not yesterday_session:
            print(f"❌ Sessione di ieri ({yesterday_date}) non trovata")
            return
        
        print(f"✅ Sessione di ieri: {yesterday_session.id} ({yesterday_session.name})")
        
        # Get messages from yesterday's session created today
        from datetime import datetime
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        messages_result = await db.execute(
            select(MessageModel)
            .where(
                MessageModel.session_id == yesterday_session.id,
                MessageModel.tenant_id == user.tenant_id,
                MessageModel.timestamp >= today_start
            )
            .order_by(MessageModel.timestamp)
        )
        messages_to_migrate = messages_result.scalars().all()
        
        print(f"\n📨 Messaggi da migrare: {len(messages_to_migrate)}")
        
        if len(messages_to_migrate) == 0:
            print("   Nessun messaggio da migrare")
            return
        
        for msg in messages_to_migrate:
            print(f"   - [{msg.role}] {msg.content[:50]}... (creato: {msg.timestamp})")
        
        # Ask for confirmation
        print(f"\n⚠️  Vuoi migrare {len(messages_to_migrate)} messaggi dalla sessione di ieri a quella odierna?")
        print("   (Questo cambierà il session_id dei messaggi)")
        response = input("   Digita 'yes' per confermare: ")
        
        if response.lower() != 'yes':
            print("❌ Migrazione annullata")
            return
        
        # Migrate messages
        migrated_count = 0
        for msg in messages_to_migrate:
            msg.session_id = today_session.id
            migrated_count += 1
        
        await db.commit()
        
        print(f"\n✅ Migrati {migrated_count} messaggi alla sessione odierna")
        print(f"   Sessione odierna ora ha {len(messages_to_migrate)} messaggi")


if __name__ == "__main__":
    user_email = sys.argv[1] if len(sys.argv) > 1 else "admin@example.com"
    print(f"🔄 Migrazione messaggi per utente: {user_email}\n")
    asyncio.run(migrate_messages(user_email))

