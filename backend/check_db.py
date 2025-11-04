#!/usr/bin/env python3
"""Check database state"""
import asyncio
from app.db.database import AsyncSessionLocal, engine
from app.models.database import Session, Message, Integration
from sqlalchemy import select, text
import sys

async def check():
    try:
        # Check migration version
        async with engine.begin() as conn:
            try:
                result = await conn.execute(text("SELECT version_num FROM alembic_version"))
                version = result.scalar()
                print(f"📊 Current migration version: {version}")
            except Exception as e:
                print(f"❌ Error checking migration: {e}")
        
        # Check sessions
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Session))
            sessions = result.scalars().all()
            print(f"\n📝 Sessions in database: {len(sessions)}")
            for s in sessions[:5]:
                print(f"  - {s.id} | {s.name} | status={s.status}")
            
            # Check messages
            result = await db.execute(select(Message))
            messages = result.scalars().all()
            print(f"\n💬 Messages in database: {len(messages)}")
            
            # Check integrations
            result = await db.execute(select(Integration))
            integrations = result.scalars().all()
            print(f"\n🔌 Integrations in database: {len(integrations)}")
            for i in integrations:
                print(f"  - {i.id} | {i.provider} | {i.service_type} | enabled={i.enabled}")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check())

