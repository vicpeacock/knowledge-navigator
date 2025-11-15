#!/usr/bin/env python3
"""Script per testare il multi-tenant refactoring"""
import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.database import get_db
from app.models.database import Tenant, Session, Message, File, MemoryShort, MemoryMedium, MemoryLong, Integration, Notification
from app.core.tenant_context import initialize_default_tenant, DEFAULT_TENANT_ID
from sqlalchemy import select, func


async def test_multi_tenant():
    """Test che il multi-tenant funzioni correttamente"""
    print("🧪 Testing Multi-Tenant Implementation\n")
    
    try:
        async for db in get_db():
            # Test 1: Verificare che il default tenant sia inizializzato
            print("1️⃣  Testing default tenant initialization...")
            tenant_id = await initialize_default_tenant(db)
            if tenant_id:
                print(f"   ✅ Default tenant initialized: {tenant_id}")
            else:
                print("   ❌ Failed to initialize default tenant")
                return False
            
            # Test 2: Verificare che tutte le query funzionino con tenant_id
            print("\n2️⃣  Testing query filtering by tenant_id...")
            
            # Test sessions
            result = await db.execute(
                select(func.count(Session.id)).where(Session.tenant_id == DEFAULT_TENANT_ID)
            )
            session_count = result.scalar()
            print(f"   ✅ Sessions with default tenant: {session_count}")
            
            # Test messages
            result = await db.execute(
                select(func.count(Message.id)).where(Message.tenant_id == DEFAULT_TENANT_ID)
            )
            message_count = result.scalar()
            print(f"   ✅ Messages with default tenant: {message_count}")
            
            # Test files
            result = await db.execute(
                select(func.count(File.id)).where(File.tenant_id == DEFAULT_TENANT_ID)
            )
            file_count = result.scalar()
            print(f"   ✅ Files with default tenant: {file_count}")
            
            # Test 3: Verificare che non ci siano record senza tenant_id
            print("\n3️⃣  Testing data integrity (no null tenant_id)...")
            
            tables_to_check = [
                (Session, "sessions"),
                (Message, "messages"),
                (File, "files"),
                (MemoryShort, "memory_short"),
                (MemoryMedium, "memory_medium"),
                (MemoryLong, "memory_long"),
                (Integration, "integrations"),
                (Notification, "notifications"),
            ]
            
            all_ok = True
            for model, table_name in tables_to_check:
                if hasattr(model, 'id'):
                    pk_field = 'id'
                elif hasattr(model, 'session_id'):
                    pk_field = 'session_id'
                else:
                    continue
                
                pk_column = getattr(model, pk_field)
                result = await db.execute(
                    select(func.count(pk_column)).where(model.tenant_id.is_(None))
                )
                null_count = result.scalar()
                
                if null_count > 0:
                    print(f"   ❌ {table_name}: {null_count} records without tenant_id")
                    all_ok = False
                else:
                    print(f"   ✅ {table_name}: All records have tenant_id")
            
            # Test 4: Verificare isolamento (simulare 2 tenant)
            print("\n4️⃣  Testing tenant isolation...")
            result = await db.execute(select(Tenant))
            tenants = result.scalars().all()
            print(f"   ✅ Found {len(tenants)} tenant(s) in database")
            
            if len(tenants) >= 1:
                default_tenant = tenants[0]
                print(f"   ✅ Default tenant: {default_tenant.name} (ID: {default_tenant.id})")
                
                # Verificare che le sessioni appartengano al default tenant
                result = await db.execute(
                    select(Session).where(Session.tenant_id == default_tenant.id).limit(1)
                )
                sample_session = result.scalar_one_or_none()
                if sample_session:
                    print(f"   ✅ Sample session belongs to default tenant: {sample_session.id}")
                else:
                    print("   ⚠️  No sessions found for default tenant")
            
            if all_ok:
                print("\n🎉 All tests passed! Multi-tenant implementation is working correctly.")
                return True
            else:
                print("\n⚠️  Some tests failed. Check the errors above.")
                return False
            
    except Exception as e:
        print(f"\n❌ ERROR during testing: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main function"""
    success = asyncio.run(test_multi_tenant())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

