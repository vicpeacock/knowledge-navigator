#!/usr/bin/env python3
"""Test database connection"""
import asyncio
import pytest
from app.db.database import AsyncSessionLocal
from sqlalchemy import text

pytestmark = pytest.mark.skip(reason="Test manuale di connessione DB: va eseguito solo all'occorrenza")

async def test():
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(text('SELECT 1'))
            print('✅ PostgreSQL connection works:', result.scalar())
            
            # Check database name
            result = await db.execute(text('SELECT current_database()'))
            db_name = result.scalar()
            print(f'✅ Connected to database: {db_name}')
            
    except Exception as e:
        print(f'❌ PostgreSQL connection failed: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())

