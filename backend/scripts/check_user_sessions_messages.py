#!/usr/bin/env python3
"""
Script per verificare tutte le sessioni e messaggi di un utente
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from app.db.database import AsyncSessionLocal
from app.models.database import Session as SessionModel, Message as MessageModel, User


async def check_user_sessions(user_email: str = "admin@example.com"):
    """Check all sessions and messages for a user"""
    
    async with AsyncSessionLocal() as db:
        # Get user
        user_result = await db.execute(
            select(User).where(User.email == user_email)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            print(f"❌ Utente {user_email} non trovato")
            return
        
        print(f"✅ Utente trovato: {user.email} (ID: {user.id})")
        print(f"   Tenant ID: {user.tenant_id}\n")
        
        # Get all sessions for this user
        sessions_result = await db.execute(
            select(SessionModel)
            .where(SessionModel.user_id == user.id)
            .order_by(SessionModel.created_at.desc())
        )
        sessions = sessions_result.scalars().all()
        
        print(f"📋 Sessioni trovate: {len(sessions)}\n")
        
        for session in sessions:
            # Count messages for this session
            messages_count_result = await db.execute(
                select(func.count(MessageModel.id))
                .where(
                    MessageModel.session_id == session.id,
                    MessageModel.tenant_id == session.tenant_id
                )
            )
            messages_count = messages_count_result.scalar_one()
            
            print(f"   Session: {session.id}")
            print(f"      Nome: {session.name}")
            print(f"      Status: {session.status}")
            print(f"      Creata: {session.created_at}")
            print(f"      Messaggi: {messages_count}")
            
            if messages_count > 0:
                # Get first and last message
                first_msg_result = await db.execute(
                    select(MessageModel)
                    .where(
                        MessageModel.session_id == session.id,
                        MessageModel.tenant_id == session.tenant_id
                    )
                    .order_by(MessageModel.timestamp.asc())
                    .limit(1)
                )
                first_msg = first_msg_result.scalar_one_or_none()
                
                last_msg_result = await db.execute(
                    select(MessageModel)
                    .where(
                        MessageModel.session_id == session.id,
                        MessageModel.tenant_id == session.tenant_id
                    )
                    .order_by(MessageModel.timestamp.desc())
                    .limit(1)
                )
                last_msg = last_msg_result.scalar_one_or_none()
                
                if first_msg:
                    print(f"      Primo messaggio: [{first_msg.role}] {first_msg.content[:50]}...")
                if last_msg:
                    print(f"      Ultimo messaggio: [{last_msg.role}] {last_msg.content[:50]}...")
            print()


if __name__ == "__main__":
    user_email = sys.argv[1] if len(sys.argv) > 1 else "admin@example.com"
    print(f"🔍 Verificando sessioni e messaggi per utente: {user_email}\n")
    asyncio.run(check_user_sessions(user_email))

