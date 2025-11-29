#!/usr/bin/env python3
"""
Script per verificare sessioni orfane o con user_id diversi
"""

import os
import sys
import asyncio
import httpx
import json
from typing import Dict, Any, List

BACKEND_URL = os.getenv('BACKEND_URL', 'https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app')

async def check_orphan_sessions():
    """Verifica sessioni orfane o con problemi"""
    
    print("🔍 Verifica Sessioni Orfane")
    print("=" * 80)
    print()
    
    email = os.getenv('TEST_EMAIL', 'admin@example.com').strip()
    password = os.getenv('TEST_PASSWORD', 'admin123').strip()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Login come admin
        print("1️⃣ Login come admin...")
        try:
            # Create/update admin
            init_response = await client.post(
                f"{BACKEND_URL}/api/init/admin",
                json={
                    "email": email,
                    "password": password,
                    "name": "Admin User"
                }
            )
            init_response.raise_for_status()
            
            # Login
            login_response = await client.post(
                f"{BACKEND_URL}/api/v1/auth/login",
                json={"email": email, "password": password}
            )
            login_response.raise_for_status()
            login_data = login_response.json()
            access_token = login_data.get("access_token")
            current_user_data = login_data.get("user", {})
            current_user_id = current_user_data.get("id")
            current_tenant_id = current_user_data.get("tenant_id")
            
            print(f"✅ Login riuscito")
            print(f"   User ID corrente: {current_user_id}")
            print(f"   Tenant ID corrente: {current_tenant_id}")
            print()
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
        except Exception as e:
            print(f"❌ Errore nel login: {e}")
            return False
        
        # 2. Verifica sessioni visibili all'utente corrente
        print("2️⃣ Sessioni visibili all'utente corrente...")
        try:
            sessions_response = await client.get(
                f"{BACKEND_URL}/api/sessions/",
                headers=headers
            )
            sessions_response.raise_for_status()
            visible_sessions = sessions_response.json()
            
            print(f"✅ Trovate {len(visible_sessions)} sessione/i visibili")
            if visible_sessions:
                print("   Sessioni visibili:")
                for session in visible_sessions[:10]:
                    print(f"      - ID: {session.get('id')}")
                    print(f"        Name: {session.get('name')}")
                    print(f"        Status: {session.get('status')}")
                    print(f"        Created: {session.get('created_at')}")
            print()
        except Exception as e:
            print(f"❌ Errore: {e}")
            visible_sessions = []
        
        # 3. Verifica sessioni archiviate
        print("3️⃣ Sessioni archiviate...")
        try:
            archived_response = await client.get(
                f"{BACKEND_URL}/api/sessions/?status=archived",
                headers=headers
            )
            archived_response.raise_for_status()
            archived_sessions = archived_response.json()
            
            print(f"✅ Trovate {len(archived_sessions)} sessione/i archiviate")
            if archived_sessions:
                print("   Prime 5 archiviate:")
                for session in archived_sessions[:5]:
                    print(f"      - ID: {session.get('id')}")
                    print(f"        Name: {session.get('name')}")
                    print(f"        Archived: {session.get('archived_at')}")
            print()
        except Exception as e:
            print(f"❌ Errore: {e}")
            archived_sessions = []
        
        # 4. Verifica utenti nel tenant (se admin può farlo)
        print("4️⃣ Verifica altri utenti nel tenant...")
        try:
            users_response = await client.get(
                f"{BACKEND_URL}/api/v1/users",
                headers=headers
            )
            users_response.raise_for_status()
            users = users_response.json()
            
            print(f"✅ Trovati {len(users)} utente/i nel tenant")
            if users:
                print("   Utenti:")
                for user in users[:10]:
                    user_id = user.get('id')
                    user_email = user.get('email')
                    user_role = user.get('role')
                    is_current = user_id == current_user_id
                    marker = "← TU" if is_current else ""
                    print(f"      - {user_email} ({user_role}) - ID: {user_id} {marker}")
                    
                    # Per ogni utente diverso, verifica le sue sessioni
                    if not is_current:
                        try:
                            # Prova a fare login con questo utente (se conosciamo la password)
                            # Ma non possiamo farlo senza password, quindi saltiamo
                            pass
                        except:
                            pass
            print()
        except Exception as e:
            print(f"⚠️  Non è possibile verificare altri utenti (potrebbe richiedere permessi admin): {e}")
            print()
        
        # 5. Analisi e raccomandazioni
        print("5️⃣ Analisi e Raccomandazioni")
        print("=" * 80)
        print()
        
        total_visible = len(visible_sessions) + len(archived_sessions)
        print(f"📊 Riepilogo:")
        print(f"   Sessioni attive visibili: {len(visible_sessions)}")
        print(f"   Sessioni archiviate: {len(archived_sessions)}")
        print(f"   Totale sessioni visibili: {total_visible}")
        print()
        
        if total_visible == 0:
            print("⚠️  Nessuna sessione trovata.")
            print("   Possibili cause:")
            print("   1. Le sessioni esistono ma con user_id diverso")
            print("   2. Le sessioni esistono ma con tenant_id diverso")
            print("   3. Le sessioni sono state eliminate")
            print("   4. C'è un problema con l'autenticazione")
            print()
            print("   Per verificare:")
            print("   - Controlla direttamente nel database Supabase")
            print("   - Query SQL: SELECT id, name, user_id, tenant_id, created_at FROM sessions")
            print("   - Verifica se ci sono sessioni con user_id diverso da", current_user_id)
        else:
            print("✅ Sessioni trovate correttamente!")
            print()
            print("   Se pensavi di avere più sessioni:")
            print("   - Verifica se sono archiviate (controlla la sezione 'Archived')")
            print("   - Verifica se sono associate a un altro utente")
            print("   - Verifica se sono state eliminate")
        
        print()
        print("=" * 80)
        
        return True

if __name__ == "__main__":
    asyncio.run(check_orphan_sessions())

