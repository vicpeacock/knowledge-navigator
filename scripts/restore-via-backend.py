#!/usr/bin/env python3
"""
Script per recuperare dati da Supabase usando il backend Cloud Run stesso come proxy
"""
import requests
import json
import os
import sys

# URL del backend Cloud Run
CLOUD_BACKEND_URL = "https://knowledge-navigator-backend-526374196058.us-central1.run.app"

# Admin credentials dal cloud (se disponibili)
ADMIN_EMAIL = "admin@example.com"  # Cambia con le credenziali reali
ADMIN_PASSWORD = "Admin123!"  # Cambia con la password reale

def get_cloud_token():
    """Login al backend cloud per ottenere il token"""
    print("🔐 Login al backend cloud...")
    response = requests.post(
        f"{CLOUD_BACKEND_URL}/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=10
    )
    if response.status_code == 200:
        data = response.json()
        return data["access_token"]
    else:
        print(f"❌ Login fallito: {response.status_code} - {response.text}")
        return None

def export_users(token):
    """Esporta users dal cloud"""
    print("👥 Esportazione users...")
    response = requests.get(
        f"{CLOUD_BACKEND_URL}/api/users",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    if response.status_code == 200:
        return response.json()
    else:
        print(f"⚠️  Errore esportazione users: {response.status_code}")
        return []

def export_sessions(token):
    """Esporta sessions dal cloud"""
    print("💬 Esportazione sessions...")
    response = requests.get(
        f"{CLOUD_BACKEND_URL}/api/sessions",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30
    )
    if response.status_code == 200:
        return response.json()
    else:
        print(f"⚠️  Errore esportazione sessions: {response.status_code}")
        return []

def main():
    print("🔄 Export dati dal Cloud Run backend")
    print("=" * 60)
    
    # Login
    token = get_cloud_token()
    if not token:
        print("❌ Impossibile autenticarsi al backend cloud")
        print("   Modifica ADMIN_EMAIL e ADMIN_PASSWORD nello script")
        sys.exit(1)
    
    print("✅ Autenticazione riuscita")
    
    # Export
    users = export_users(token)
    sessions = export_sessions(token)
    
    # Salva in file JSON
    export_data = {
        "users": users,
        "sessions": sessions,
    }
    
    with open("/tmp/knowledge_navigator_export.json", "w") as f:
        json.dump(export_data, f, indent=2, default=str)
    
    print(f"\n✅ Export completato: /tmp/knowledge_navigator_export.json")
    print(f"   - {len(users)} users")
    print(f"   - {len(sessions)} sessions")
    print("\nOra puoi importare i dati nel database locale")

if __name__ == "__main__":
    main()

