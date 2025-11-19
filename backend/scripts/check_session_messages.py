#!/usr/bin/env python3
"""
Script per verificare i messaggi di una sessione nel database
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
from app.models.database import Session as SessionModel, Message as MessageModel, User, Tenant


async def check_session_messages(session_id: str):
    """Check messages for a session"""
    session_uuid = UUID(session_id)
    
    async with AsyncSessionLocal() as db:
        # Get session
        session_result = await db.execute(
            select(SessionModel).where(SessionModel.id == session_uuid)
        )
        session = session_result.scalar_one_or_none()
        
        if not session:
            print(f"❌ Sessione {session_id} non trovata nel database")
            return
        
        print(f"✅ Sessione trovata:")
        print(f"   ID: {session.id}")
        print(f"   Nome: {session.name}")
        print(f"   Status: {session.status}")
        print(f"   Tenant ID: {session.tenant_id}")
        print(f"   User ID: {session.user_id}")
        print(f"   Creata: {session.created_at}")
        print(f"   Aggiornata: {session.updated_at}")
        
        # Get tenant
        tenant_result = await db.execute(
            select(Tenant).where(Tenant.id == session.tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()
        if tenant:
            print(f"   Tenant: {tenant.name}")
        
        # Get user
        if session.user_id:
            user_result = await db.execute(
                select(User).where(User.id == session.user_id)
            )
            user = user_result.scalar_one_or_none()
            if user:
                print(f"   User: {user.email}")
        
        # Get messages
        messages_result = await db.execute(
            select(MessageModel)
            .where(
                MessageModel.session_id == session_uuid,
                MessageModel.tenant_id == session.tenant_id
            )
            .order_by(MessageModel.timestamp)
        )
        messages = messages_result.scalars().all()
        
        print(f"\n📨 Messaggi trovati: {len(messages)}")
        
        if len(messages) == 0:
            print("   ⚠️  Nessun messaggio trovato per questa sessione!")
            
            # Check if there are messages with wrong tenant_id
            all_messages_result = await db.execute(
                select(MessageModel).where(MessageModel.session_id == session_uuid)
            )
            all_messages = all_messages_result.scalars().all()
            
            if len(all_messages) > 0:
                print(f"\n   ⚠️  ATTENZIONE: Trovati {len(all_messages)} messaggi con session_id={session_id} ma tenant_id diverso!")
                for msg in all_messages:
                    print(f"      - Message ID: {msg.id}, Tenant ID: {msg.tenant_id} (sessione ha tenant_id: {session.tenant_id})")
        else:
            print("\n   Messaggi:")
            for i, msg in enumerate(messages, 1):
                print(f"   {i}. [{msg.role}] {msg.content[:100]}...")
                print(f"      Timestamp: {msg.timestamp}")
                print(f"      Tenant ID: {msg.tenant_id}")
                print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_session_messages.py <session_id>")
        sys.exit(1)
    
    session_id = sys.argv[1]
    print(f"🔍 Verificando messaggi per sessione: {session_id}\n")
    asyncio.run(check_session_messages(session_id))

