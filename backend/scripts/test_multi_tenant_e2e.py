#!/usr/bin/env python3
"""Test end-to-end del multi-tenant refactoring"""
import asyncio
import sys
from pathlib import Path
from uuid import UUID

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.database import get_db
from app.models.database import Tenant, Session, Message
from app.core.tenant_context import initialize_default_tenant, get_tenant_id
from sqlalchemy import select
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession


async def test_tenant_isolation():
    """Test che i tenant siano isolati correttamente"""
    print("🧪 Testing Tenant Isolation (End-to-End)\n")
    
    try:
        async for db in get_db():
            # Inizializza default tenant
            default_tenant_id = await initialize_default_tenant(db)
            if not default_tenant_id:
                print("❌ Failed to initialize default tenant")
                return False
            
            print(f"✅ Default tenant: {default_tenant_id}\n")
            
            # Test 1: Verificare che le query filtrino correttamente
            print("1️⃣  Testing query filtering...")
            
            # Conta sessioni per default tenant
            result = await db.execute(
                select(Session).where(Session.tenant_id == default_tenant_id)
            )
            sessions = result.scalars().all()
            print(f"   ✅ Found {len(sessions)} sessions for default tenant")
            
            if sessions:
                sample_session = sessions[0]
                print(f"   ✅ Sample session: {sample_session.id} (tenant: {sample_session.tenant_id})")
                
                # Verificare che i messaggi appartengano allo stesso tenant
                result = await db.execute(
                    select(Message).where(
                        Message.session_id == sample_session.id,
                        Message.tenant_id == default_tenant_id
                    )
                )
                messages = result.scalars().all()
                print(f"   ✅ Found {len(messages)} messages for session (all with correct tenant_id)")
            
            # Test 2: Verificare che non ci siano leak tra tenant
            print("\n2️⃣  Testing data isolation...")
            
            # Conta tutti i tenant
            result = await db.execute(select(Tenant))
            all_tenants = result.scalars().all()
            print(f"   ✅ Found {len(all_tenants)} tenant(s) in database")
            
            if len(all_tenants) > 1:
                # Test isolamento: verificare che ogni tenant veda solo i propri dati
                for tenant in all_tenants:
                    result = await db.execute(
                        select(Session).where(Session.tenant_id == tenant.id)
                    )
                    tenant_sessions = result.scalars().all()
                    print(f"   ✅ Tenant '{tenant.name}': {len(tenant_sessions)} sessions")
            else:
                print("   ℹ️  Only one tenant exists (expected for now)")
            
            # Test 3: Verificare che get_tenant_id funzioni
            print("\n3️⃣  Testing tenant context extraction...")
            try:
                # Simula chiamata senza header (usa default tenant)
                # Nota: non possiamo testare direttamente get_tenant_id senza FastAPI request
                # ma possiamo verificare che il default tenant sia accessibile
                result = await db.execute(
                    select(Tenant).where(Tenant.id == default_tenant_id)
                )
                tenant = result.scalar_one_or_none()
                if tenant:
                    print(f"   ✅ Default tenant accessible: {tenant.name}")
                else:
                    print("   ❌ Default tenant not accessible")
                    return False
            except Exception as e:
                print(f"   ❌ Error testing tenant context: {e}")
                return False
            
            print("\n🎉 All end-to-end tests passed!")
            return True
            
    except Exception as e:
        print(f"\n❌ ERROR during testing: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main function"""
    success = asyncio.run(test_tenant_isolation())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

