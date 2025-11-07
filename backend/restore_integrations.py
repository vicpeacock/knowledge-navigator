#!/usr/bin/env python3
"""
Script per verificare e ripristinare le integrazioni
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.db.database import AsyncSessionLocal
from app.models.database import Integration


async def restore_integrations():
    """Verifica e ripristina tutte le integrazioni"""
    async with AsyncSessionLocal() as db:
        try:
            # Get all integrations
            result = await db.execute(select(Integration))
            integrations = result.scalars().all()
            
            print(f"📊 Trovate {len(integrations)} integrazioni nel database:\n")
            
            if not integrations:
                print("❌ Nessuna integrazione trovata nel database.")
                print("   Le integrazioni devono essere riconfigurate tramite l'interfaccia web.")
                return
            
            # Restore all integrations (enable them)
            restored_count = 0
            for integration in integrations:
                status = "✅ abilitata" if integration.enabled else "❌ disabilitata"
                print(f"  • {integration.service_type.upper()} ({integration.provider})")
                print(f"    ID: {integration.id}")
                print(f"    Stato: {status}")
                print(f"    Credenziali: {'Presenti' if integration.credentials_encrypted else 'Mancanti'}")
                
                # Enable integration if disabled
                if not integration.enabled:
                    integration.enabled = True
                    restored_count += 1
                    print(f"    🔧 Riabilitata!")
                
                print()
            
            if restored_count > 0:
                await db.commit()
                print(f"✅ Riabilitate {restored_count} integrazione/i\n")
            
            # Summary
            enabled_count = sum(1 for i in integrations if i.enabled)
            print(f"\n📈 Riepilogo:")
            print(f"   Totale integrazioni: {len(integrations)}")
            print(f"   Abilitate: {enabled_count}")
            print(f"   Disabilitate: {len(integrations) - enabled_count}")
            
            # Group by type
            calendar_count = sum(1 for i in integrations if i.service_type == "calendar")
            email_count = sum(1 for i in integrations if i.service_type == "email")
            mcp_count = sum(1 for i in integrations if i.service_type == "mcp_server")
            
            print(f"\n📦 Per tipo:")
            if calendar_count > 0:
                print(f"   📅 Calendario: {calendar_count}")
            if email_count > 0:
                print(f"   📧 Email: {email_count}")
            if mcp_count > 0:
                print(f"   🔌 MCP Server: {mcp_count}")
            
            print("\n✅ Verifica completata!")
            
        except Exception as e:
            print(f"❌ Errore durante la verifica: {e}")
            import traceback
            traceback.print_exc()
            await db.rollback()


if __name__ == "__main__":
    print("🔍 Verifica e ripristino integrazioni...\n")
    asyncio.run(restore_integrations())

