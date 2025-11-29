#!/usr/bin/env python3
"""
Script per testare le connessioni ai database e verificare le sessioni
"""

import os
import sys
import asyncio
import httpx
import json
from typing import Dict, Any, Optional

BACKEND_URL = os.getenv('BACKEND_URL', 'https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app')

async def test_database_connections():
    """Test delle connessioni ai database e verifica delle sessioni"""
    
    print("🔍 Test Connessioni Database e Sessioni")
    print("=" * 80)
    print()
    
    # 0. Crea admin user se necessario
    print("0️⃣ Creazione/aggiornamento admin user...")
    email = os.getenv('TEST_EMAIL', 'admin@example.com').strip()
    password = os.getenv('TEST_PASSWORD', 'admin123').strip()
    
    if len(sys.argv) >= 3:
        email = sys.argv[1].strip()
        password = sys.argv[2].strip()
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                init_response = await client.post(
                    f"{BACKEND_URL}/api/init/admin",
                    json={
                        "email": email,
                        "password": password,
                        "name": "Test Admin"
                    }
                )
                init_response.raise_for_status()
                init_data = init_response.json()
                print(f"✅ Admin user creato/aggiornato: {init_data.get('email')}")
                print()
            except Exception as e:
                print(f"⚠️  Errore nella creazione admin (potrebbe già esistere): {e}")
                print()
            
            # 1. Health check
            print("1️⃣ Health Check - Verifica connessioni database...")
            try:
                health_response = await client.get(f"{BACKEND_URL}/health")
                health_response.raise_for_status()
                health_data = health_response.json()
                
                print(f"✅ Health check riuscito")
                print(f"   All healthy: {health_data.get('all_healthy')}")
                print(f"   All mandatory healthy: {health_data.get('all_mandatory_healthy')}")
                print()
                
                services = health_data.get('services', {})
                for service_name, service_status in services.items():
                    healthy = service_status.get('healthy', False)
                    mandatory = service_status.get('mandatory', False)
                    message = service_status.get('message', '')
                    status_icon = "✅" if healthy else "❌"
                    mandatory_icon = "🔴" if mandatory else "🟡"
                    print(f"   {status_icon} {mandatory_icon} {service_name}: {message}")
                print()
                
                if not health_data.get('all_healthy'):
                    print("⚠️  Alcuni servizi non sono healthy!")
                    unhealthy = health_data.get('unhealthy_services', [])
                    if unhealthy:
                        print(f"   Servizi non healthy: {unhealthy}")
                    print()
            except Exception as e:
                print(f"❌ Errore nel health check: {e}")
                return False
            
            # 2. Login
            print("2️⃣ Login per ottenere token JWT...")
            try:
                login_response = await client.post(
                    f"{BACKEND_URL}/api/v1/auth/login",
                    json={"email": email, "password": password}
                )
                login_response.raise_for_status()
                login_data = login_response.json()
                access_token = login_data.get("access_token")
                
                if not access_token:
                    print("❌ Token non ricevuto dal login")
                    return False
                
                print(f"✅ Login riuscito")
                print(f"   Token length: {len(access_token)}")
                print()
                
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
            except Exception as e:
                print(f"❌ Errore nel login: {e}")
                if hasattr(e, 'response'):
                    print(f"   Response: {e.response.text[:500]}")
                return False
            
            # 3. Verifica utente
            print("3️⃣ Verifica informazioni utente...")
            try:
                user_response = await client.get(
                    f"{BACKEND_URL}/api/v1/users/me",
                    headers=headers
                )
                user_response.raise_for_status()
                user_data = user_response.json()
                user_id = user_data.get('id')
                tenant_id = user_data.get('tenant_id')
                
                print(f"✅ Utente: {user_data.get('email')}")
                print(f"   User ID: {user_id}")
                print(f"   Tenant ID: {tenant_id}")
                print()
            except Exception as e:
                print(f"❌ Errore nel recupero utente: {e}")
                return False
            
            # 4. Lista sessioni
            print("4️⃣ Verifica sessioni esistenti...")
            try:
                sessions_response = await client.get(
                    f"{BACKEND_URL}/api/sessions/",
                    headers=headers
                )
                sessions_response.raise_for_status()
                sessions = sessions_response.json()
                
                print(f"✅ Trovate {len(sessions)} sessione/i")
                if sessions:
                    print("   Sessioni:")
                    for session in sessions[:10]:  # Mostra prime 10
                        print(f"      - ID: {session.get('id')}")
                        print(f"        Name: {session.get('name')}")
                        print(f"        Status: {session.get('status')}")
                        print(f"        Created: {session.get('created_at')}")
                        print(f"        Updated: {session.get('updated_at')}")
                        print()
                else:
                    print("   ⚠️  Nessuna sessione trovata")
                    print("   Questo potrebbe essere normale se è la prima volta che usi l'applicazione")
                    print()
            except Exception as e:
                print(f"❌ Errore nel recupero sessioni: {e}")
                if hasattr(e, 'response'):
                    print(f"   Status: {e.response.status_code}")
                    print(f"   Response: {e.response.text[:500]}")
                print()
            
            # 5. Test creazione sessione
            print("5️⃣ Test creazione nuova sessione...")
            try:
                create_response = await client.post(
                    f"{BACKEND_URL}/api/sessions/",
                    headers=headers,
                    json={
                        "name": "Test Session",
                        "title": "Test Session Title",
                        "description": "Test session created by database connection test"
                    }
                )
                create_response.raise_for_status()
                new_session = create_response.json()
                
                print(f"✅ Sessione creata con successo!")
                print(f"   ID: {new_session.get('id')}")
                print(f"   Name: {new_session.get('name')}")
                print()
            except Exception as e:
                print(f"❌ Errore nella creazione sessione: {e}")
                if hasattr(e, 'response'):
                    print(f"   Status: {e.response.status_code}")
                    print(f"   Response: {e.response.text[:500]}")
                print()
            
            # 6. Verifica sessioni dopo creazione
            print("6️⃣ Verifica sessioni dopo creazione...")
            try:
                sessions_response = await client.get(
                    f"{BACKEND_URL}/api/sessions/",
                    headers=headers
                )
                sessions_response.raise_for_status()
                sessions = sessions_response.json()
                
                print(f"✅ Trovate {len(sessions)} sessione/i")
                if sessions:
                    print("   Prime 5 sessioni:")
                    for session in sessions[:5]:
                        print(f"      - {session.get('name')} ({session.get('id')})")
                print()
            except Exception as e:
                print(f"❌ Errore nel recupero sessioni: {e}")
                print()
            
            print("=" * 80)
            print("✅ Test completato")
            
            return True
    except Exception as e:
        print(f"❌ Errore generale: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_database_connections())
    sys.exit(0 if success else 1)

