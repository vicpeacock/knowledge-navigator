#!/usr/bin/env python3
"""
Script completo per esportare TUTTI i dati dal backend Cloud Run:
- Users
- Sessions (per ogni utente)
- Messages (per ogni sessione)
- Files (per ogni utente)
- Integrations (per ogni utente)
- Notifications (per ogni utente)
- Memory (long-term memories)
"""
import requests
import json
import sys
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

CLOUD_BACKEND_URL = "https://knowledge-navigator-backend-526374196058.us-central1.run.app"

def get_token(email: str, password: str) -> str:
    """Login e ottiene il token"""
    print(f"🔐 Login come {email}...")
    response = requests.post(
        f"{CLOUD_BACKEND_URL}/api/v1/auth/login",
        json={"email": email, "password": password},
        timeout=30
    )
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        print(f"❌ Login fallito: {response.status_code} - {response.text}")
        return None

def export_users(token: str) -> List[Dict]:
    """Esporta tutti gli users"""
    print("👥 Esportazione users...")
    response = requests.get(
        f"{CLOUD_BACKEND_URL}/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    if response.status_code == 200:
        users = response.json()
        print(f"   ✅ {len(users)} users")
        return users
    else:
        print(f"   ❌ Errore: {response.status_code}")
        return []

def export_user_sessions(token: str) -> List[Dict]:
    """Esporta le sessioni dell'utente corrente"""
    print("   💬 Esportazione sessions...")
    response = requests.get(
        f"{CLOUD_BACKEND_URL}/api/v1/sessions/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    if response.status_code == 200:
        sessions = response.json()
        print(f"      ✅ {len(sessions)} sessions")
        return sessions
    else:
        print(f"      ❌ Errore: {response.status_code}")
        return []

def export_session_messages(token: str, session_id: str) -> List[Dict]:
    """Esporta i messaggi di una sessione"""
    response = requests.get(
        f"{CLOUD_BACKEND_URL}/api/v1/sessions/{session_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    if response.status_code == 200:
        return response.json()
    else:
        return []

def export_session_memory(token: str, session_id: str) -> Dict:
    """Esporta la memoria di una sessione"""
    response = requests.get(
        f"{CLOUD_BACKEND_URL}/api/v1/sessions/{session_id}/memory",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    if response.status_code == 200:
        return response.json()
    else:
        return {}

def export_user_files(token: str) -> List[Dict]:
    """Esporta i file dell'utente corrente"""
    print("   📁 Esportazione files...")
    response = requests.get(
        f"{CLOUD_BACKEND_URL}/api/v1/files/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    if response.status_code == 200:
        files = response.json()
        print(f"      ✅ {len(files)} files")
        return files
    else:
        print(f"      ❌ Errore: {response.status_code}")
        return []

def export_user_integrations(token: str) -> List[Dict]:
    """Esporta le integrazioni dell'utente corrente"""
    print("   🔌 Esportazione integrations...")
    try:
        # Prova endpoint MCP integrations
        response = requests.get(
            f"{CLOUD_BACKEND_URL}/api/v1/integrations/mcp/integrations",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30
        )
        if response.status_code == 200:
            integrations = response.json()
            print(f"      ✅ {len(integrations)} integrations (MCP)")
            return integrations
    except:
        pass
    
    # Fallback: prova altri endpoint
    integrations = []
    print(f"      ⚠️  Nessuna integration trovata o endpoint non disponibile")
    return integrations

def export_user_notifications(token: str) -> List[Dict]:
    """Esporta le notifiche dell'utente corrente"""
    print("   🔔 Esportazione notifications...")
    response = requests.get(
        f"{CLOUD_BACKEND_URL}/api/v1/notifications/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    if response.status_code == 200:
        notifications = response.json()
        print(f"      ✅ {len(notifications)} notifications")
        return notifications
    else:
        print(f"      ❌ Errore: {response.status_code}")
        return []

def main():
    print("🔄 Export COMPLETO di tutti i dati dal Cloud Run")
    print("=" * 60)
    
    # Credenziali admin
    admin_email = "admin@example.com"
    admin_password = "admin123"
    
    # Login come admin
    admin_token = get_token(admin_email, admin_password)
    if not admin_token:
        print("❌ Impossibile autenticarsi come admin")
        sys.exit(1)
    
    print("✅ Login admin riuscito\n")
    
    # Export users
    all_users = export_users(admin_token)
    
    if not all_users:
        print("❌ Nessun user trovato")
        sys.exit(1)
    
    # Per ogni utente, esporta i suoi dati
    all_data = {
        "export_date": datetime.now().isoformat(),
        "users": all_users,
        "user_data": {}  # Dati per utente
    }
    
    print(f"\n📦 Esportazione dati per {len(all_users)} users...\n")
    
    for user in all_users:
        user_email = user.get("email")
        user_id = user.get("id")
        
        print(f"\n👤 User: {user_email} (ID: {user_id})")
        
        # Per esportare i dati di un utente, dovremmo fare login come quell'utente
        # Ma non abbiamo le password! Quindi possiamo solo esportare:
        # - Dati che l'admin può vedere (users, ecc.)
        # - Dati pubblici
        
        # Se è l'admin, possiamo esportare i suoi dati
        if user_email == admin_email:
            user_token = admin_token
            
            # Export sessions per questo utente
            sessions = export_user_sessions(user_token)
            all_data["user_data"][user_id] = {
                "email": user_email,
                "sessions": sessions,
                "messages": {},  # session_id -> messages
                "memory": {},    # session_id -> memory
                "files": [],
                "integrations": [],
                "notifications": []
            }
            
            # Export messages per ogni sessione
            for session in sessions:
                session_id = session.get("id")
                print(f"      📨 Esportazione messaggi per sessione {session_id}...")
                messages = export_session_messages(user_token, session_id)
                all_data["user_data"][user_id]["messages"][session_id] = messages
                print(f"         ✅ {len(messages)} messages")
                
                # Export memory
                print(f"      🧠 Esportazione memoria per sessione {session_id}...")
                memory = export_session_memory(user_token, session_id)
                all_data["user_data"][user_id]["memory"][session_id] = memory
            
            # Export files
            files = export_user_files(user_token)
            all_data["user_data"][user_id]["files"] = files
            
            # Export integrations
            integrations = export_user_integrations(user_token)
            all_data["user_data"][user_id]["integrations"] = integrations
            
            # Export notifications
            notifications = export_user_notifications(user_token)
            all_data["user_data"][user_id]["notifications"] = notifications
        else:
            # Per altri utenti, possiamo solo salvare le informazioni base
            print(f"   ⚠️  Password non disponibile - solo dati base")
            all_data["user_data"][user_id] = {
                "email": user_email,
                "note": "Password non disponibile - dati completi non esportati"
            }
    
    # Salva tutto in un file JSON
    output_file = Path("/tmp/knowledge_navigator_full_export.json")
    with open(output_file, "w") as f:
        json.dump(all_data, f, indent=2, default=str)
    
    print(f"\n✅ Export completato!")
    print(f"   File: {output_file}")
    print(f"\n📊 Riepilogo:")
    print(f"   - Users: {len(all_users)}")
    total_sessions = sum(len(ud.get("sessions", [])) for ud in all_data["user_data"].values())
    total_messages = sum(sum(len(msgs) for msgs in ud.get("messages", {}).values()) for ud in all_data["user_data"].values())
    total_files = sum(len(ud.get("files", [])) for ud in all_data["user_data"].values())
    print(f"   - Sessions: {total_sessions}")
    print(f"   - Messages: {total_messages}")
    print(f"   - Files: {total_files}")
    
    print(f"\n⚠️  NOTA: Per esportare i dati completi di tutti gli utenti,")
    print(f"   è necessario avere le loro password o creare un endpoint admin")
    print(f"   che permetta l'esportazione completa.")

if __name__ == "__main__":
    main()

