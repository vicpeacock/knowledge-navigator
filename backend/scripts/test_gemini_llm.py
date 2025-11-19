#!/usr/bin/env python3
"""
Script per testare che Gemini LLM risponda correttamente
"""
import asyncio
import httpx
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = "http://localhost:8000"

async def test_gemini_llm():
    """Test che Gemini LLM risponda correttamente"""
    
    # Credenziali admin
    email = "admin@example.com"
    password = "admin123"
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        print("=" * 60)
        print("🧪 TEST GEMINI LLM")
        print("=" * 60)
        
        # Step 1: Login
        print("\n1️⃣  Login...")
        try:
            login_response = await client.post(
                f"{BASE_URL}/api/v1/auth/login",
                json={"email": email, "password": password}
            )
            
            if login_response.status_code != 200:
                print(f"   ❌ Login failed: {login_response.status_code}")
                print(f"   Response: {login_response.text}")
                return False
            
            token = login_response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            print(f"   ✅ Login successful")
        except Exception as e:
            print(f"   ❌ Login error: {e}")
            return False
        
        # Step 2: Get or create session
        print("\n2️⃣  Get/Create session...")
        try:
            sessions_response = await client.get(
                f"{BASE_URL}/api/sessions",
                headers=headers
            )
            
            if sessions_response.status_code != 200:
                print(f"   ❌ Get sessions failed: {sessions_response.status_code}")
                return False
            
            sessions = sessions_response.json()
            if sessions and len(sessions) > 0:
                session_id = sessions[0]["id"]
                print(f"   ✅ Using existing session: {session_id[:8]}...")
            else:
                # Create new session
                create_response = await client.post(
                    f"{BASE_URL}/api/sessions",
                    headers=headers,
                    json={"name": "Test Gemini Session"}
                )
                if create_response.status_code != 200:
                    print(f"   ❌ Create session failed: {create_response.status_code}")
                    return False
                session_id = create_response.json()["id"]
                print(f"   ✅ Created new session: {session_id[:8]}...")
        except Exception as e:
            print(f"   ❌ Session error: {e}")
            return False
        
        # Step 3: Test chat with Gemini
        print("\n3️⃣  Test chat con Gemini...")
        print("   📝 Messaggio: 'Dimmi solo OK se mi senti e stai usando Gemini'")
        
        try:
            chat_response = await client.post(
                f"{BASE_URL}/api/sessions/{session_id}/chat",
                headers=headers,
                json={
                    "message": "Dimmi solo OK se mi senti e stai usando Gemini",
                    "use_memory": False,
                    "force_web_search": False
                },
                timeout=120.0
            )
            
            print(f"   Status: {chat_response.status_code}")
            
            if chat_response.status_code == 200:
                result = chat_response.json()
                response_text = result.get("response", "")
                tools_used = result.get("tools_used", [])
                agent_activity = result.get("agent_activity", [])
                
                print(f"\n   ✅ Risposta ricevuta!")
                print(f"   📝 Lunghezza risposta: {len(response_text)} caratteri")
                print(f"   📝 Risposta: {response_text[:200]}{'...' if len(response_text) > 200 else ''}")
                print(f"   🔧 Tools usati: {len(tools_used)}")
                if tools_used:
                    print(f"      {', '.join(tools_used)}")
                print(f"   🤖 Eventi agent: {len(agent_activity)}")
                
                # Verifica che la risposta contenga qualcosa di sensato
                if len(response_text) > 0:
                    print(f"\n   ✅ TEST PASSATO: Gemini ha risposto correttamente!")
                    return True
                else:
                    print(f"\n   ⚠️  Risposta vuota")
                    return False
            else:
                print(f"   ❌ Chat failed: {chat_response.status_code}")
                print(f"   Response: {chat_response.text[:500]}")
                return False
                
        except httpx.TimeoutException:
            print(f"   ❌ Timeout: La richiesta ha impiegato troppo tempo")
            return False
        except Exception as e:
            print(f"   ❌ Chat error: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        print("\n" + "=" * 60)

if __name__ == "__main__":
    success = asyncio.run(test_gemini_llm())
    sys.exit(0 if success else 1)

