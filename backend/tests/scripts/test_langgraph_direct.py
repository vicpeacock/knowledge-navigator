#!/usr/bin/env python3
"""
Script per testare direttamente LangGraph chiamando l'endpoint /chat del backend.
"""
import asyncio
import httpx
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

async def test_langgraph():
    """Test LangGraph chiamando direttamente l'endpoint /chat."""
    base_url = "http://localhost:8000"
    
    # Credenziali admin
    email = "admin@example.com"
    password = "admin123"
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        print("🔐 Step 1: Login...")
        # Login
        login_response = await client.post(
            f"{base_url}/api/v1/auth/login",
            json={"email": email, "password": password}
        )
        
        if login_response.status_code != 200:
            print(f"❌ Login failed: {login_response.status_code}")
            print(login_response.text)
            return
        
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"✅ Login successful, token: {token[:30]}...")
        
        print("\n📋 Step 2: Get sessions...")
        # Get sessions
        sessions_response = await client.get(
            f"{base_url}/api/sessions",
            headers=headers
        )
        
        if sessions_response.status_code != 200:
            print(f"❌ Get sessions failed: {sessions_response.status_code}")
            print(sessions_response.text)
            return
        
        sessions = sessions_response.json()
        if not sessions:
            print("❌ No sessions found")
            return
        
        session_id = sessions[0]["id"]
        print(f"✅ Using session: {session_id}")
        
        print("\n💬 Step 3: Send chat message...")
        print("   Message: 'Test: dimmi solo OK se mi senti'")
        # Send chat message
        chat_response = await client.post(
            f"{base_url}/api/sessions/{session_id}/chat",
            headers=headers,
            json={
                "message": "Test: dimmi solo OK se mi senti",
                "use_memory": True,
                "force_web_search": False
            },
            timeout=120.0  # Longer timeout for LangGraph execution
        )
        
        print(f"Status code: {chat_response.status_code}")
        if chat_response.status_code == 200:
            result = chat_response.json()
            print(f"✅ Response received:")
            print(f"   Response text length: {len(result.get('response', ''))}")
            print(f"   Response preview: {result.get('response', '')[:200]}")
            print(f"   Tools used: {result.get('tools_used', [])}")
            print(f"   Agent activity: {len(result.get('agent_activity', []))} events")
        else:
            print(f"❌ Chat failed: {chat_response.status_code}")
            print(chat_response.text)

if __name__ == "__main__":
    asyncio.run(test_langgraph())

