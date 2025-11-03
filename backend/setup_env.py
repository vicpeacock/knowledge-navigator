#!/usr/bin/env python3
"""
Script helper per configurare il file .env per Google Calendar
"""
import secrets
import os
from pathlib import Path

def generate_encryption_key():
    """Genera una chiave di crittografia sicura di 32 caratteri"""
    return secrets.token_urlsafe(32)

def create_env_file():
    """Crea o aggiorna il file .env"""
    env_path = Path(__file__).parent / ".env"
    
    print("=" * 60)
    print("🔧 Setup Google Calendar - Configurazione .env")
    print("=" * 60)
    print()
    
    # Controlla se il file esiste
    existing_values = {}
    if env_path.exists():
        print("📄 File .env trovato. Leggo i valori esistenti...")
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    existing_values[key.strip()] = value.strip()
        print("✅ Valori esistenti caricati")
        print()
    
    # Richiedi Client ID
    print("1️⃣ Google Client ID")
    print("   Vai su: https://console.cloud.google.com/")
    print("   APIs & Services > Credentials > Crea OAuth client ID")
    print("   Tipo: Web application")
    print()
    
    current_client_id = existing_values.get('GOOGLE_CLIENT_ID', '')
    if current_client_id:
        use_existing = input(f"   Client ID esistente: {current_client_id[:30]}...\n   Usarlo? (s/n, default=s): ").strip().lower()
        if use_existing == 'n':
            client_id = input("   Inserisci nuovo Google Client ID: ").strip()
        else:
            client_id = current_client_id
    else:
        client_id = input("   Inserisci Google Client ID: ").strip()
    
    # Richiedi Client Secret
    print()
    print("2️⃣ Google Client Secret")
    print("   (Inizia con GOCSPX-...)")
    print()
    
    current_client_secret = existing_values.get('GOOGLE_CLIENT_SECRET', '')
    if current_client_secret:
        use_existing = input(f"   Client Secret esistente: {current_client_secret[:15]}...\n   Usarlo? (s/n, default=s): ").strip().lower()
        if use_existing == 'n':
            client_secret = input("   Inserisci nuovo Google Client Secret: ").strip()
        else:
            client_secret = current_client_secret
    else:
        client_secret = input("   Inserisci Google Client Secret: ").strip()
    
    # Genera encryption key se non esiste
    print()
    print("3️⃣ Chiave di Crittografia")
    encryption_key = existing_values.get('CREDENTIALS_ENCRYPTION_KEY', generate_encryption_key())
    if encryption_key == generate_encryption_key():  # Se è quella di default
        print(f"   ✅ Generata automaticamente: {encryption_key[:30]}...")
    else:
        print(f"   ✅ Usa chiave esistente: {encryption_key[:30]}...")
    
    # Redirect URI (fisso)
    redirect_uri = "http://localhost:8000/api/integrations/calendars/oauth/callback"
    
    # Scrive il file .env
    print()
    print("4️⃣ Scrittura file .env...")
    
    # Legge contenuto esistente se presente
    env_content = []
    other_lines = []
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                stripped = line.strip()
                # Mantieni linee vuote e commenti, rimuovi solo quelle che stiamo sovrascrivendo
                if any(key in line for key in ['GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'GOOGLE_REDIRECT_URI', 'CREDENTIALS_ENCRYPTION_KEY']):
                    continue  # Skip, lo riscriviamo
                other_lines.append(line.rstrip('\n'))
    
    # Aggiungi le nuove variabili
    env_content.extend(other_lines)
    
    # Aggiungi sezione Google Calendar se non c'è già
    if not any('Google Calendar' in line for line in env_content):
        env_content.append('')
        env_content.append('# Google OAuth2 Credentials (for Calendar/Email)')
    
    env_content.append(f'GOOGLE_CLIENT_ID={client_id}')
    env_content.append(f'GOOGLE_CLIENT_SECRET={client_secret}')
    env_content.append(f'GOOGLE_REDIRECT_URI={redirect_uri}')
    env_content.append('')
    env_content.append('# Encryption Key for storing credentials securely')
    env_content.append(f'CREDENTIALS_ENCRYPTION_KEY={encryption_key}')
    
    # Scrivi il file
    with open(env_path, 'w') as f:
        f.write('\n'.join(env_content) + '\n')
    
    print(f"✅ File .env creato/aggiornato: {env_path}")
    print()
    print("=" * 60)
    print("✅ Configurazione completata!")
    print("=" * 60)
    print()
    print("📝 Prossimi passi:")
    print("   1. Riavvia il backend per caricare le nuove variabili")
    print("   2. Vai su http://localhost:3003/integrations")
    print("   3. Clicca 'Connetti Google Calendar'")
    print()
    
    # Verifica che i valori siano corretti
    print("🔍 Verifica configurazione:")
    print(f"   ✓ Client ID: {client_id[:30]}..." if len(client_id) > 30 else f"   ✓ Client ID: {client_id}")
    print(f"   ✓ Client Secret: {client_secret[:15]}..." if len(client_secret) > 15 else f"   ✓ Client Secret: {client_secret}")
    print(f"   ✓ Redirect URI: {redirect_uri}")
    print(f"   ✓ Encryption Key: {encryption_key[:30]}...")
    print()

if __name__ == "__main__":
    try:
        create_env_file()
    except KeyboardInterrupt:
        print("\n\n❌ Operazione annullata")
    except Exception as e:
        print(f"\n\n❌ Errore: {e}")
        import traceback
        traceback.print_exc()

