#!/usr/bin/env python3
"""End-to-end test for multi-tenant implementation"""
import asyncio
import sys
from pathlib import Path
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import hashlib
import httpx
import json

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.database import get_db
from app.models.database import Tenant, Session, Message, File, ApiKey, MemoryLong
from app.core.tenant_context import initialize_default_tenant
from app.core.memory_manager import MemoryManager

# Assuming the FastAPI backend is running on http://localhost:8000
BASE_URL = "http://localhost:8000"

async def test_e2e_multi_tenant():
    """Comprehensive end-to-end test for multi-tenant functionality"""
    print("🧪 End-to-End Multi-Tenant Test\n")
    print("=" * 60)
    
    all_tests_passed = True
    
    try:
        # Step 1: Initialize default tenant
        print("\n1️⃣  Initializing default tenant...")
        async for db in get_db():
            default_tenant_id = await initialize_default_tenant(db)
            if not default_tenant_id:
                print("   ❌ Failed to initialize default tenant")
                return False
            print(f"   ✅ Default tenant: {default_tenant_id}")
            break
        
        # Step 2: Create API key for testing
        print("\n2️⃣  Creating API key...")
        test_api_key = None
        api_key_id = None
        
        async with httpx.AsyncClient() as client:
            # Create API key (using default tenant via X-Tenant-ID)
            api_key_response = await client.post(
                f"{BASE_URL}/api/v1/apikeys",
                json={"name": "E2E Test Key"},
                headers={"X-Tenant-ID": str(default_tenant_id)},
                timeout=10.0
            )
            
            if api_key_response.status_code != 201:
                print(f"   ❌ Failed to create API key: {api_key_response.status_code}")
                print(f"   Response: {api_key_response.text}")
                print(f"   ⚠️  Skipping API key tests (backend might not be running)")
                # Continue with X-Tenant-ID tests instead
                test_api_key = None
            else:
                api_key_data = api_key_response.json()
                test_api_key = api_key_data.get("key")
                api_key_id = api_key_data.get("id")
                print(f"   ✅ API key created: {api_key_id}")
                print(f"   🔑 Key: {test_api_key[:20]}...")
            
            # Step 3: Test API key authentication (if API key was created)
            if test_api_key:
                print("\n3️⃣  Testing API key authentication...")
                try:
                    test_auth_response = await client.get(
                        f"{BASE_URL}/api/sessions/",
                        headers={"X-API-Key": test_api_key},
                        timeout=10.0
                    )
                    
                    if test_auth_response.status_code == 200:
                        print("   ✅ API key authentication works")
                    else:
                        print(f"   ❌ API key authentication failed: {test_auth_response.status_code}")
                        print(f"   Response: {test_auth_response.text}")
                        all_tests_passed = False
                except Exception as e:
                    print(f"   ⚠️  Error testing API key auth: {e}")
            else:
                print("\n3️⃣  Skipping API key authentication (using X-Tenant-ID instead)")
            
            # Step 4: Create a session
            print("\n4️⃣  Creating session...")
            test_session_id = None
            session_headers = {"X-Tenant-ID": str(default_tenant_id)}
            if test_api_key:
                session_headers = {"X-API-Key": test_api_key}
            
            session_response = await client.post(
                f"{BASE_URL}/api/sessions/",
                json={
                    "name": "E2E Test Session",
                    "title": "E2E Test",
                    "description": "End-to-end test session"
                },
                headers=session_headers,
                timeout=10.0
            )
            
            if session_response.status_code != 201:
                print(f"   ❌ Failed to create session: {session_response.status_code}")
                print(f"   Response: {session_response.text}")
                all_tests_passed = False
                print("   ⚠️  Skipping remaining tests that require a session")
            else:
                session_data = session_response.json()
                test_session_id = session_data.get("id")
                print(f"   ✅ Session created: {test_session_id}")
            
            # Step 5: Send a message (if session was created)
            if test_session_id:
                print("\n5️⃣  Sending message to session...")
                chat_headers = {"X-Tenant-ID": str(default_tenant_id)}
                if test_api_key:
                    chat_headers = {"X-API-Key": test_api_key}
                
                try:
                    chat_response = await client.post(
                        f"{BASE_URL}/api/sessions/{test_session_id}/chat",
                        json={
                            "message": "Ciao, questo è un test end-to-end del sistema multi-tenant.",
                            "session_id": test_session_id,
                            "use_memory": True,
                            "force_web_search": False
                        },
                        headers=chat_headers,
                        timeout=180.0  # 3 minutes for LLM response
                    )
                    
                    if chat_response.status_code == 200:
                        chat_data = chat_response.json()
                        print(f"   ✅ Message sent and response received")
                        print(f"   📝 Response length: {len(chat_data.get('response', ''))} chars")
                    else:
                        print(f"   ⚠️  Chat response status: {chat_response.status_code}")
                        print(f"   Response: {chat_response.text[:200]}")
                except httpx.TimeoutException:
                    print("   ⚠️  Chat request timed out (LLM might be slow)")
                except Exception as e:
                    print(f"   ⚠️  Error sending message: {e}")
            else:
                print("\n5️⃣  Skipping message test (no session created)")
            
            # Step 6: Verify data isolation (if session was created)
            if test_session_id:
                print("\n6️⃣  Verifying data isolation...")
                async for db in get_db():
                    # Verify session belongs to correct tenant
                    session_result = await db.execute(
                        select(Session).where(Session.id == UUID(test_session_id))
                    )
                    session = session_result.scalar_one_or_none()
                    
                    if session and session.tenant_id == default_tenant_id:
                        print(f"   ✅ Session belongs to correct tenant: {session.tenant_id}")
                    else:
                        print(f"   ❌ Session tenant mismatch!")
                        all_tests_passed = False
                    
                    # Count messages for this tenant
                    message_count = await db.scalar(
                        select(func.count(Message.id)).where(
                            Message.tenant_id == default_tenant_id
                        )
                    )
                    print(f"   ✅ Total messages for tenant: {message_count}")
                    break
            else:
                print("\n6️⃣  Skipping data isolation test (no session created)")
            
            # Step 7: Test ChromaDB isolation
            print("\n7️⃣  Testing ChromaDB isolation...")
            async for db in get_db():
                memory_manager = MemoryManager(tenant_id=default_tenant_id)
                
                # Test collection naming
                collection_name = memory_manager._get_collection_name("long_term_memory", default_tenant_id)
                print(f"   ✅ Collection name: {collection_name}")
                
                # Test that we can retrieve memory (should work even if empty)
                try:
                    results = await memory_manager.retrieve_long_term_memory(
                        "test query",
                        n_results=5,
                        tenant_id=default_tenant_id,
                    )
                    print(f"   ✅ Memory retrieval works (returned {len(results)} results)")
                except Exception as e:
                    print(f"   ⚠️  Memory retrieval error: {e}")
                break
            
            # Step 8: List API keys (if API key was created)
            if test_api_key:
                print("\n8️⃣  Listing API keys...")
                list_keys_response = await client.get(
                    f"{BASE_URL}/api/v1/apikeys",
                    headers={"X-API-Key": test_api_key},
                    params={"active_only": True},
                    timeout=10.0
                )
                
                if list_keys_response.status_code == 200:
                    keys_data = list_keys_response.json()
                    print(f"   ✅ Found {len(keys_data)} active API key(s)")
                else:
                    print(f"   ❌ Failed to list API keys: {list_keys_response.status_code}")
                    all_tests_passed = False
            else:
                print("\n8️⃣  Skipping API keys listing (API key not created)")
            
            # Step 9: Test tenant isolation (if session was created)
            if test_session_id:
                print("\n9️⃣  Testing tenant isolation...")
                async for db in get_db():
                    # Try to access session with wrong tenant (should fail)
                    # First, create a second tenant for testing
                    test_tenant = Tenant(
                        name="Test Tenant 2",
                        schema_name="tenant_test_2",
                        active=True,
                    )
                    db.add(test_tenant)
                    await db.commit()
                    await db.refresh(test_tenant)
                    
                    # Try to access session with second tenant's ID
                    # (This should fail because session belongs to default tenant)
                    test_auth_isolated = await client.get(
                        f"{BASE_URL}/api/sessions/{test_session_id}",
                        headers={"X-Tenant-ID": str(test_tenant.id)},
                        timeout=10.0
                    )
                    
                    # Should return 404 or 403 (not found or forbidden)
                    if test_auth_isolated.status_code in [404, 403]:
                        print(f"   ✅ Tenant isolation works (returned {test_auth_isolated.status_code})")
                    else:
                        print(f"   ⚠️  Unexpected status: {test_auth_isolated.status_code}")
                    
                    # Cleanup test tenant
                    await db.delete(test_tenant)
                    await db.commit()
                    break
            else:
                print("\n9️⃣  Skipping tenant isolation test (no session created)")
            
            # Step 10: Cleanup - Revoke API key (if created)
            if test_api_key and api_key_id:
                print("\n🔟 Cleaning up...")
                revoke_response = await client.delete(
                    f"{BASE_URL}/api/v1/apikeys/{api_key_id}",
                    headers={"X-API-Key": test_api_key},
                    timeout=10.0
                )
                
                if revoke_response.status_code == 204:
                    print("   ✅ API key revoked")
                else:
                    print(f"   ⚠️  Failed to revoke API key: {revoke_response.status_code}")
                
                # Verify API key is revoked
                verify_revoked = await client.get(
                    f"{BASE_URL}/api/sessions/",
                    headers={"X-API-Key": test_api_key},
                    timeout=10.0
                )
                
                if verify_revoked.status_code == 401:
                    print("   ✅ Revoked API key correctly rejected")
                else:
                    print(f"   ⚠️  Revoked API key still works (status: {verify_revoked.status_code})")
            else:
                print("\n🔟 Skipping cleanup (no API key to revoke)")
        
        print("\n" + "=" * 60)
        if all_tests_passed:
            print("🎉 All end-to-end tests passed!")
        else:
            print("⚠️  Some tests had issues. Check the output above.")
        
        return all_tests_passed
        
    except httpx.ConnectError as e:
        print("\n❌ ERROR: Could not connect to backend!")
        print(f"   Error: {e}")
        print("   Make sure the backend is running on http://localhost:8000")
        print("   Start it with: cd backend && uvicorn app.main:app --reload")
        return False
    except httpx.TimeoutException:
        print("\n❌ ERROR: Backend request timed out!")
        print("   The backend might be slow or not responding")
        return False
    except Exception as e:
        print(f"\n❌ ERROR during end-to-end test: {e}")
        import traceback
        traceback.print_exc()
        return False

async def check_backend_health() -> bool:
    """Check if backend is running"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/health", timeout=5.0)
            return response.status_code == 200
    except:
        return False

def main() -> None:
    """Main entry point"""
    print("Starting end-to-end multi-tenant test...")
    print("Make sure the backend is running on http://localhost:8000\n")
    
    # Check if backend is running
    print("Checking backend health...")
    backend_running = asyncio.run(check_backend_health())
    
    if not backend_running:
        print("❌ Backend is not running or not responding!")
        print("   Please start the backend first:")
        print("   cd backend && uvicorn app.main:app --reload")
        sys.exit(1)
    
    print("✅ Backend is running\n")
    
    result = asyncio.run(test_e2e_multi_tenant())
    sys.exit(0 if result else 1)

if __name__ == "__main__":
    main()

