#!/usr/bin/env python3
"""Test and generate Fernet encryption key"""
from cryptography.fernet import Fernet
import base64
import os

def test_key(key: str):
    """Test if a key is valid for Fernet"""
    try:
        key_bytes = key.encode()[:32].ljust(32, b'0')
        key_b64 = base64.urlsafe_b64encode(key_bytes)
        f = Fernet(key_b64)
        print(f"✅ Chiave valida!")
        print(f"   Originale: {key}")
        print(f"   Base64: {key_b64.decode()}")
        return True
    except Exception as e:
        print(f"❌ Errore: {e}")
        return False

def generate_key():
    """Generate a valid Fernet key"""
    key = Fernet.generate_key()
    print(f"✅ Chiave generata:")
    print(f"   {key.decode()}")
    return key.decode()

if __name__ == "__main__":
    # Test current key from .env
    current_key = os.getenv("CREDENTIALS_ENCRYPTION_KEY", "your-32-byte-encryption-key-change-me")
    print(f"🔍 Testando chiave corrente: {current_key}")
    is_valid = test_key(current_key)
    
    if not is_valid:
        print("\n🔧 Generando nuova chiave valida...")
        new_key = generate_key()
        print(f"\n📝 Aggiungi questa riga al tuo .env:")
        print(f"CREDENTIALS_ENCRYPTION_KEY={new_key}")

