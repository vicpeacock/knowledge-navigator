#!/usr/bin/env python3
"""Test JSONB save/retrieve"""
import asyncio
import sys
from pathlib import Path
from uuid import UUID

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.db.database import AsyncSessionLocal
from app.models.database import Integration
from sqlalchemy import select, text

async def test_jsonb():
    """Test JSONB save/retrieve directly"""
    async with AsyncSessionLocal() as db:
        integration_id = UUID("67465695-76d2-4036-94a4-9c8db7047d6a")
        
        # Get integration
        result = await db.execute(
            select(Integration)
            .where(Integration.id == integration_id)
        )
        integration = result.scalar_one_or_none()
        
        if not integration:
            print("❌ Integration not found")
            return
        
        print(f"✅ Found integration: {integration.id}")
        
        # Get current metadata
        current_metadata = integration.session_metadata or {}
        print(f"\n📋 Current metadata keys: {list(current_metadata.keys())}")
        
        # Add test data
        test_data = {"test_key": "test_value", "oauth_credentials": {"test_user": "encrypted_data"}}
        integration.session_metadata = {**current_metadata, **test_data}
        
        print(f"\n💾 Saving test data...")
        print(f"   New metadata keys: {list(integration.session_metadata.keys())}")
        
        try:
            await db.commit()
            print(f"✅ Commit successful")
        except Exception as e:
            print(f"❌ Commit failed: {e}")
            import traceback
            traceback.print_exc()
            await db.rollback()
            return
        
        # Query directly from database (bypassing SQLAlchemy cache)
        print(f"\n🔍 Querying directly from database...")
        result = await db.execute(
            text("SELECT metadata FROM integrations WHERE id = :id"),
            {"id": str(integration_id)}
        )
        row = result.fetchone()
        if row:
            db_metadata = row[0] if row[0] else {}
            print(f"✅ Direct query successful")
            print(f"   Metadata keys from DB: {list(db_metadata.keys()) if isinstance(db_metadata, dict) else 'Not a dict'}")
            print(f"   Has test_key: {'test_key' in db_metadata if isinstance(db_metadata, dict) else False}")
            print(f"   Has oauth_credentials: {'oauth_credentials' in db_metadata if isinstance(db_metadata, dict) else False}")
        else:
            print(f"❌ No row found")
        
        # Now refresh and check
        print(f"\n🔄 Refreshing integration...")
        await db.refresh(integration)
        refreshed_metadata = integration.session_metadata or {}
        print(f"   Metadata keys after refresh: {list(refreshed_metadata.keys())}")
        print(f"   Has test_key: {'test_key' in refreshed_metadata}")
        print(f"   Has oauth_credentials: {'oauth_credentials' in refreshed_metadata}")

if __name__ == "__main__":
    asyncio.run(test_jsonb())

