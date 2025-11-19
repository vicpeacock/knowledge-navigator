#!/usr/bin/env python3
"""
Script per verificare e pulire integrazioni con credenziali corrotte o non decrittabili.

Usage:
    python backend/scripts/check_and_clean_integrations.py [--clean] [--provider google] [--service-type email|calendar]
"""
import asyncio
import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import AsyncSessionLocal
from app.models.database import Integration
from app.core.config import settings
import json
import base64
from cryptography.fernet import Fernet


def _decrypt_credentials(encrypted: str, key: str) -> dict:
    """Decrypt credentials from storage"""
    try:
        key_bytes = key.encode()[:32].ljust(32, b'0')
        key_b64 = base64.urlsafe_b64encode(key_bytes)
        f = Fernet(key_b64)
        decrypted = f.decrypt(encrypted.encode())
        return json.loads(decrypted.decode())
    except Exception as e:
        raise ValueError(f"Error decrypting credentials: {str(e)}")


async def check_integrations(
    db: AsyncSession,
    provider: str = None,
    service_type: str = None,
    clean: bool = False
):
    """Check integrations for corrupted credentials"""
    
    print("=" * 80)
    print("🔍 VERIFICA INTEGRAZIONI")
    print("=" * 80)
    print(f"Provider: {provider or 'Tutti'}")
    print(f"Service Type: {service_type or 'Tutti'}")
    print(f"Chiave crittografia: {settings.credentials_encryption_key[:20]}...")
    print()
    
    # Build query
    query = select(Integration).where(Integration.enabled == True)
    if provider:
        query = query.where(Integration.provider == provider)
    if service_type:
        query = query.where(Integration.service_type == service_type)
    
    result = await db.execute(query)
    integrations = result.scalars().all()
    
    if not integrations:
        print("✅ Nessuna integrazione trovata con i filtri specificati.")
        return
    
    print(f"📋 Trovate {len(integrations)} integrazione/i attiva/e\n")
    
    corrupted = []
    valid = []
    
    for integration in integrations:
        print(f"🔍 Verificando: {integration.provider} - {integration.service_type} (ID: {integration.id})")
        print(f"   Tenant: {integration.tenant_id}")
        print(f"   User: {integration.user_id or 'N/A'}")
        print(f"   Enabled: {integration.enabled}")
        
        try:
            # Try to decrypt credentials
            credentials = _decrypt_credentials(
                integration.credentials_encrypted,
                settings.credentials_encryption_key
            )
            
            # Check if credentials have required fields
            required_fields = ["token", "refresh_token"]
            missing_fields = [f for f in required_fields if f not in credentials]
            
            if missing_fields:
                print(f"   ⚠️  Credenziali decrittate ma mancano campi: {', '.join(missing_fields)}")
                corrupted.append((integration, f"Missing fields: {', '.join(missing_fields)}"))
            else:
                print(f"   ✅ Credenziali valide (token presente, refresh_token presente)")
                valid.append(integration)
                
        except ValueError as e:
            error_msg = str(e)
            print(f"   ❌ ERRORE DECRITTAZIONE: {error_msg}")
            corrupted.append((integration, error_msg))
        except Exception as e:
            print(f"   ❌ ERRORE GENERICO: {e}")
            corrupted.append((integration, str(e)))
        
        print()
    
    # Summary
    print("=" * 80)
    print("📊 RIEPILOGO")
    print("=" * 80)
    print(f"✅ Integrazioni valide: {len(valid)}")
    print(f"❌ Integrazioni corrotte: {len(corrupted)}")
    print()
    
    if corrupted:
        print("🔴 INTEGRAZIONI CORROTTE:")
        for integration, error in corrupted:
            print(f"   - {integration.provider} - {integration.service_type} (ID: {integration.id})")
            print(f"     Errore: {error}")
            print(f"     Tenant: {integration.tenant_id}")
            print(f"     User: {integration.user_id or 'N/A'}")
            print()
        
        if clean:
            print("🧹 PULIZIA INTEGRAZIONI CORROTTE...")
            print()
            
            for integration, error in corrupted:
                try:
                    # Disable instead of delete to preserve history
                    integration.enabled = False
                    await db.commit()
                    print(f"   ✅ Disabilitata integrazione {integration.id} ({integration.provider} - {integration.service_type})")
                except Exception as e:
                    print(f"   ❌ Errore disabilitando integrazione {integration.id}: {e}")
                    await db.rollback()
            
            print()
            print("✅ Pulizia completata!")
            print()
            print("📝 PROSSIMI PASSI:")
            print("   1. Vai alla pagina delle integrazioni")
            print("   2. Riconnetti Gmail e Calendar tramite OAuth")
            print("   3. Le nuove credenziali verranno salvate correttamente")
        else:
            print("💡 Per pulire le integrazioni corrotte, esegui:")
            print(f"   python {sys.argv[0]} --clean")
            if provider:
                print(f"   python {sys.argv[0]} --clean --provider {provider}")
            if service_type:
                print(f"   python {sys.argv[0]} --clean --service-type {service_type}")
    else:
        print("✅ Tutte le integrazioni sono valide!")


async def main():
    parser = argparse.ArgumentParser(
        description="Verifica e pulisce integrazioni con credenziali corrotte"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Disabilita le integrazioni corrotte (default: solo verifica)"
    )
    parser.add_argument(
        "--provider",
        type=str,
        help="Filtra per provider (es: google)"
    )
    parser.add_argument(
        "--service-type",
        type=str,
        choices=["email", "calendar"],
        help="Filtra per tipo di servizio"
    )
    
    args = parser.parse_args()
    
    async with AsyncSessionLocal() as db:
        try:
            await check_integrations(
                db=db,
                provider=args.provider,
                service_type=args.service_type,
                clean=args.clean
            )
        except Exception as e:
            print(f"❌ Errore: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

