#!/usr/bin/env python3
"""
Script per debuggare il problema delle sessioni mancanti
"""

import os
import sys
import asyncio
import httpx
import json

BACKEND_URL = os.getenv('BACKEND_URL', 'https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app')

async def debug_sessions():
    """Debug del problema delle sessioni"""
    
    print("🔍 Debug Problema Sessioni")
    print("=" * 80)
    print()
    
    email = os.getenv('TEST_EMAIL', 'admin@example.com').strip()
    password = os.getenv('TEST_PASSWORD', 'admin123').strip()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Crea/aggiorna admin
        print("1️⃣ Creazione/aggiornamento admin user...")
        try:
            init_response = await client.post(
                f"{BACKEND_URL}/api/init/admin",
                json={
                    "email": email,
                    "password": password,
                    "name": "Admin User"
                }
            )
            init_response.raise_for_status()
            init_data = init_response.json()
            print(f"✅ Admin user creato/aggiornato")
            print(f"   Email: {init_data.get('email')}")
            print(f"   User ID: {init_data.get('id')}")
            print(f"   Tenant ID: {init_data.get('tenant_id')}")
            print()
        except Exception as e:
            print(f"❌ Errore: {e}")
            return False
        
        # 2. Login
        print("2️⃣ Login...")
        try:
            login_response = await client.post(
                f"{BACKEND_URL}/api/v1/auth/login",
                json={"email": email, "password": password}
            )
            login_response.raise_for_status()
            login_data = login_response.json()
            access_token = login_data.get("access_token")
            user_data = login_data.get("user", {})
            
            print(f"✅ Login riuscito")
            print(f"   User ID dal login: {user_data.get('id')}")
            print(f"   Email: {user_data.get('email')}")
            print(f"   Tenant ID: {user_data.get('tenant_id')}")
            print()
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
        except Exception as e:
            print(f"❌ Errore nel login: {e}")
            return False
        
        # 3. Verifica utente corrente
        print("3️⃣ Verifica utente corrente (/api/v1/users/me)...")
        try:
            me_response = await client.get(
                f"{BACKEND_URL}/api/v1/users/me",
                headers=headers
            )
            me_response.raise_for_status()
            me_data = me_response.json()
            current_user_id = me_data.get('id')
            current_email = me_data.get('email')
            current_tenant_id = me_data.get('tenant_id')
            
            print(f"✅ Utente corrente:")
            print(f"   User ID: {current_user_id}")
            print(f"   Email: {current_email}")
            print(f"   Tenant ID: {current_tenant_id}")
            print()
        except Exception as e:
            print(f"❌ Errore: {e}")
            return False
        
        # 4. Lista sessioni (con filtro user_id)
        print("4️⃣ Lista sessioni per utente corrente...")
        try:
            sessions_response = await client.get(
                f"{BACKEND_URL}/api/sessions/?status=active",
                headers=headers
            )
            sessions_response.raise_for_status()
            sessions = sessions_response.json()
            
            print(f"✅ Trovate {len(sessions)} sessione/i attive")
            if sessions:
                print("   Sessioni:")
                for session in sessions[:5]:
                    print(f"      - ID: {session.get('id')}")
                    print(f"        Name: {session.get('name')}")
                    print(f"        Created: {session.get('created_at')}")
            else:
                print("   ⚠️  Nessuna sessione trovata")
            print()
        except Exception as e:
            print(f"❌ Errore: {e}")
            if hasattr(e, 'response'):
                print(f"   Status: {e.response.status_code}")
                print(f"   Response: {e.response.text[:500]}")
            print()
        
        # 5. Query diretta al database per vedere TUTTE le sessioni (senza filtro user_id)
        print("5️⃣ Verifica sessioni nel database (tutte, senza filtro user_id)...")
        print("   ⚠️  Questo richiede accesso diretto al database, non disponibile via API")
        print("   Possibili cause:")
        print("   1. Le sessioni esistono ma con user_id diverso da quello corrente")
        print("   2. Le sessioni esistono ma con tenant_id diverso")
        print("   3. Le sessioni sono state archiviate o eliminate")
        print("   4. L'utente admin è stato ricreato con un nuovo user_id")
        print()
        
        # 6. Verifica se ci sono sessioni con user_id NULL o diverso
        print("6️⃣ Analisi del problema:")
        print(f"   Se le sessioni esistono ma non vengono trovate, potrebbe essere che:")
        print(f"   - Le sessioni hanno user_id = {current_user_id} (corretto)")
        print(f"   - Ma l'utente admin è stato ricreato con un nuovo ID")
        print(f"   - Quindi le sessioni vecchie hanno un user_id diverso")
        print()
        print(f"   Soluzione:")
        print(f"   - Verificare nel database se ci sono sessioni con user_id diverso da {current_user_id}")
        print(f"   - Se sì, aggiornare le sessioni per assegnarle al nuovo user_id")
        print()
        
        return True

if __name__ == "__main__":
    asyncio.run(debug_sessions())

