#!/usr/bin/env python3
"""Script per testare le migration multi-tenant"""
import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.database import get_db
from app.models.database import Tenant, Session, Message, File, MemoryShort, MemoryMedium, MemoryLong, Integration, Notification
from sqlalchemy import select, func


async def test_migration():
    """Test che le migration siano state applicate correttamente"""
    try:
        async for db in get_db():
            # Test 1: Verificare che la tabella tenants esista e abbia il default tenant
            result = await db.execute(
                select(Tenant).where(Tenant.schema_name == "tenant_default")
            )
            default_tenant = result.scalar_one_or_none()
            
            if not default_tenant:
                print("❌ ERRORE: Default tenant non trovato!")
                return False
            
            print(f"✅ Default tenant trovato: {default_tenant.name} (ID: {default_tenant.id})")
            
            # Test 2: Verificare che tutte le tabelle abbiano tenant_id
            tables_to_check = [
                (Session, "sessions", "id"),
                (Message, "messages", "id"),
                (File, "files", "id"),
                (MemoryShort, "memory_short", "session_id"),  # MemoryShort usa session_id come primary key
                (MemoryMedium, "memory_medium", "id"),
                (MemoryLong, "memory_long", "id"),
                (Integration, "integrations", "id"),
                (Notification, "notifications", "id"),
            ]
            
            all_ok = True
            for model, table_name, pk_field in tables_to_check:
                # Contare record senza tenant_id (non dovrebbero esserci)
                pk_column = getattr(model, pk_field)
                result = await db.execute(
                    select(func.count(pk_column)).where(model.tenant_id.is_(None))
                )
                null_count = result.scalar()
                
                if null_count > 0:
                    print(f"❌ ERRORE: {table_name} ha {null_count} record senza tenant_id!")
                    all_ok = False
                else:
                    # Contare record totali
                    result = await db.execute(select(func.count(pk_column)))
                    total = result.scalar()
                    print(f"✅ {table_name}: {total} record, tutti con tenant_id")
            
            # Test 3: Verificare che le sessioni esistenti abbiano tenant_id
            result = await db.execute(
                select(func.count(Session.id)).where(Session.tenant_id == default_tenant.id)
            )
            sessions_with_tenant = result.scalar()
            
            result = await db.execute(select(func.count(Session.id)))
            total_sessions = result.scalar()
            
            if sessions_with_tenant == total_sessions:
                print(f"✅ Tutte le {total_sessions} sessioni hanno il default tenant_id")
            else:
                print(f"⚠️  WARNING: {sessions_with_tenant}/{total_sessions} sessioni hanno tenant_id")
                all_ok = False
            
            if all_ok:
                print("\n🎉 Tutti i test sono passati! Le migration sono state applicate correttamente.")
            else:
                print("\n⚠️  Alcuni test sono falliti. Controlla gli errori sopra.")
            
            return all_ok
            
    except Exception as e:
        print(f"❌ ERRORE durante il test: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main function"""
    success = asyncio.run(test_migration())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

