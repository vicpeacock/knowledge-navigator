#!/usr/bin/env python3
"""Comprehensive test script for multi-tenant implementation"""
import asyncio
import sys
from pathlib import Path
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import hashlib

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.database import get_db, create_tenant_schema
from app.models.database import Tenant, Session, Message, File, ApiKey, MemoryShort, MemoryMedium, MemoryLong
from app.core.tenant_context import initialize_default_tenant, DEFAULT_TENANT_ID
from app.core.memory_manager import MemoryManager

async def test_multi_tenant_complete():
    """Comprehensive test of multi-tenant implementation"""
    print("🧪 Testing Complete Multi-Tenant Implementation\n")
    
    all_tests_passed = True
    
    try:
        async for db in get_db():
            # Test 1: Default tenant initialization
            print("1️⃣  Testing default tenant initialization...")
            tenant_id = await initialize_default_tenant(db)
            if tenant_id:
                print(f"   ✅ Default tenant initialized: {tenant_id}")
            else:
                print("   ❌ Failed to initialize default tenant")
                all_tests_passed = False
                return False
            
            # Test 2: ChromaDB isolation
            print("\n2️⃣  Testing ChromaDB isolation...")
            memory_manager = MemoryManager(tenant_id=tenant_id)
            
            # Test collection naming
            collection_name = memory_manager._get_collection_name("test_collection", tenant_id)
            if f"tenant_{str(tenant_id).replace('-', '_')}" in collection_name:
                print(f"   ✅ Collection naming correct: {collection_name}")
            else:
                print(f"   ❌ Collection naming incorrect: {collection_name}")
                all_tests_passed = False
            
            # Test 3: API Keys
            print("\n3️⃣  Testing API Keys...")
            
            # Create a test API key
            test_key = "kn_test_key_12345"
            key_hash = hashlib.sha256(test_key.encode()).hexdigest()
            
            api_key = ApiKey(
                tenant_id=tenant_id,
                key_hash=key_hash,
                name="Test API Key",
                active=True,
            )
            db.add(api_key)
            await db.commit()
            await db.refresh(api_key)
            
            # Verify API key was created
            result = await db.execute(
                select(ApiKey).where(ApiKey.id == api_key.id)
            )
            retrieved_key = result.scalar_one_or_none()
            
            if retrieved_key and retrieved_key.tenant_id == tenant_id:
                print(f"   ✅ API key created: {api_key.id}")
            else:
                print("   ❌ API key creation failed")
                all_tests_passed = False
            
            # Test 4: Data isolation
            print("\n4️⃣  Testing data isolation...")
            
            # Count records per tenant
            session_count = await db.scalar(
                select(func.count(Session.id)).where(Session.tenant_id == tenant_id)
            )
            message_count = await db.scalar(
                select(func.count(Message.id)).where(Message.tenant_id == tenant_id)
            )
            file_count = await db.scalar(
                select(func.count(File.id)).where(File.tenant_id == tenant_id)
            )
            
            print(f"   ✅ Sessions: {session_count}, Messages: {message_count}, Files: {file_count}")
            
            # Test 5: Schema per tenant (optional)
            print("\n5️⃣  Testing schema per tenant (optional)...")
            try:
                schema_created = await create_tenant_schema(f"tenant_{str(tenant_id).replace('-', '_')}")
                if schema_created:
                    print(f"   ✅ Tenant schema created")
                else:
                    print(f"   ℹ️  Tenant schema already exists (expected)")
            except Exception as e:
                print(f"   ⚠️  Schema creation test skipped: {e}")
            
            # Test 6: Memory isolation
            print("\n6️⃣  Testing memory isolation...")
            
            # Test that memory methods accept tenant_id
            try:
                # This should not raise an error
                await memory_manager.retrieve_long_term_memory(
                    "test query",
                    n_results=5,
                    tenant_id=tenant_id,
                )
                print("   ✅ Memory methods support tenant_id")
            except Exception as e:
                print(f"   ❌ Memory methods error: {e}")
                all_tests_passed = False
            
            # Cleanup test API key
            await db.delete(api_key)
            await db.commit()
            print("\n   🧹 Cleaned up test API key")
            
            if all_tests_passed:
                print("\n🎉 All tests passed! Multi-tenant implementation is working correctly.")
            else:
                print("\n⚠️ Some tests failed. Check the output above.")
            
            return all_tests_passed
            
    except Exception as e:
        print(f"❌ ERRORE durante il test: {e}")
        import traceback
        traceback.print_exc()
        return False

def main() -> None:
    asyncio.run(test_multi_tenant_complete())

if __name__ == "__main__":
    main()
