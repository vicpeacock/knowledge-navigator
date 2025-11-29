#!/usr/bin/env python3
"""
Test locale per verificare che Vertex AI funzioni correttamente
Testa: login, creazione sessione, chat semplice
"""

import requests
import json
import sys

BACKEND_URL = "http://localhost:8000"

def test_health():
    """Test health check"""
    print("1️⃣ Health Check...")
    try:
        response = requests.get(f"{BACKEND_URL}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Backend healthy: {data.get('all_healthy')}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_init_admin():
    """Crea/aggiorna admin user"""
    print("\n2️⃣ Init Admin User...")
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/init/admin",
            json={"email": "admin@example.com", "password": "admin123", "name": "Admin User"},
            timeout=5
        )
        if response.status_code in [200, 201]:
            print("✅ Admin user created/updated")
            return True
        else:
            print(f"⚠️  Init admin: {response.status_code} - {response.text[:100]}")
            return True  # Potrebbe già esistere
    except Exception as e:
        print(f"❌ Init admin error: {e}")
        return False

def test_login():
    """Test login"""
    print("\n3️⃣ Login...")
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "admin123"},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            if token:
                print(f"✅ Login successful, token length: {len(token)}")
                return token
        print(f"❌ Login failed: {response.status_code} - {response.text[:200]}")
        return None
    except Exception as e:
        print(f"❌ Login error: {e}")
        return None

def test_create_session(token):
    """Crea una sessione"""
    print("\n4️⃣ Create Session...")
    try:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        response = requests.post(
            f"{BACKEND_URL}/api/sessions/",
            headers=headers,
            json={"name": "Test Local Session"},
            timeout=5
        )
        if response.status_code in [200, 201]:
            data = response.json()
            session_id = data.get("id")
            print(f"✅ Session created: {session_id}")
            return session_id
        print(f"❌ Create session failed: {response.status_code} - {response.text[:200]}")
        return None
    except Exception as e:
        print(f"❌ Create session error: {e}")
        return None

def test_chat(token, session_id):
    """Test chat semplice"""
    print("\n5️⃣ Test Chat (messaggio semplice)...")
    try:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        
        # Prima richiesta - potrebbe avere day_transition_pending
        response = requests.post(
            f"{BACKEND_URL}/api/sessions/{session_id}/chat",
            headers=headers,
            json={
                "message": "Ciao, come stai? Rispondi brevemente.",
                "session_id": session_id,
                "use_memory": True,
                "force_web_search": False,
                "proceed_with_new_day": False,
                "stay_on_previous_day": False
            },
            timeout=60  # Chat può richiedere tempo
        )
        
        if response.status_code == 200:
            data = response.json()
            # Se c'è day_transition_pending, procedi con la nuova sessione
            if data.get("day_transition_pending"):
                new_session_id = data.get("new_session_id")
                print(f"⚠️  Day transition detected, using new session: {new_session_id}")
                session_id = new_session_id
                # Riprova con proceed_with_new_day=True
                response = requests.post(
                    f"{BACKEND_URL}/api/sessions/{session_id}/chat",
                    headers=headers,
                    json={
                        "message": "Ciao, come stai? Rispondi brevemente.",
                        "session_id": session_id,
                        "use_memory": True,
                        "force_web_search": False,
                        "proceed_with_new_day": True,
                        "stay_on_previous_day": False
                    },
                    timeout=60
                )
        if response.status_code == 200:
            data = response.json()
            response_text = data.get("response", "")
            if response_text:
                print(f"✅ Chat successful!")
                print(f"   Response preview: {response_text[:200]}...")
                return True
            else:
                print(f"⚠️  Chat response empty")
                print(f"   Full response: {json.dumps(data, indent=2)}")
                return False
        else:
            print(f"❌ Chat failed: {response.status_code}")
            print(f"   Error: {response.text[:500]}")
            return False
    except Exception as e:
        print(f"❌ Chat error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🧪 Test Locale Vertex AI Fix")
    print("=" * 60)
    
    # Test health
    if not test_health():
        print("\n❌ Health check failed, exiting")
        sys.exit(1)
    
    # Init admin
    if not test_init_admin():
        print("\n⚠️  Init admin failed, but continuing...")
    
    # Login
    token = test_login()
    if not token:
        print("\n❌ Login failed, exiting")
        sys.exit(1)
    
    # Create session
    session_id = test_create_session(token)
    if not session_id:
        print("\n❌ Create session failed, exiting")
        sys.exit(1)
    
    # Test chat
    if test_chat(token, session_id):
        print("\n✅✅✅ TUTTI I TEST PASSATI! ✅✅✅")
        print("\nIl fix per Vertex AI System Role sembra funzionare correttamente.")
    else:
        print("\n❌❌❌ TEST CHAT FALLITO ❌❌❌")
        print("\nVerifica i log del backend per dettagli sull'errore.")
        sys.exit(1)

if __name__ == "__main__":
    main()

