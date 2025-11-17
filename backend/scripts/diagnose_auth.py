#!/usr/bin/env python3
"""Script per diagnosticare problemi di autenticazione e database"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import AsyncSessionLocal, engine
from app.models.database import User, Tenant, Session as SessionModel
from sqlalchemy import select
from uuid import UUID


async def diagnose():
    """Diagnostica problemi di autenticazione e database"""
    print("🔍 Diagnostica Autenticazione e Database\n")
    
    # Test connessione database
    print("1. Test connessione database...")
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Tenant).limit(1))
            tenant = result.scalar_one_or_none()
            if tenant:
                print(f"   ✅ Database connesso")
                print(f"   ✅ Tenant trovato: {tenant.name} (ID: {tenant.id})")
            else:
                print(f"   ⚠️  Database connesso ma nessun tenant trovato")
    except Exception as e:
        print(f"   ❌ Errore connessione database: {e}")
        return
    
    # Lista tutti i tenant
    print("\n2. Lista tenant...")
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Tenant))
            tenants = result.scalars().all()
            if tenants:
                for tenant in tenants:
                    print(f"   - {tenant.name} (ID: {tenant.id}, Active: {tenant.active})")
            else:
                print("   ⚠️  Nessun tenant trovato nel database")
    except Exception as e:
        print(f"   ❌ Errore: {e}")
    
    # Lista tutti gli utenti
    print("\n3. Lista utenti...")
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User))
            users = result.scalars().all()
            if users:
                for user in users:
                    print(f"   - {user.email} (ID: {user.id}, Tenant: {user.tenant_id}, Active: {user.active})")
            else:
                print("   ⚠️  Nessun utente trovato nel database")
    except Exception as e:
        print(f"   ❌ Errore: {e}")
    
    # Lista tutte le sessioni
    print("\n4. Lista sessioni...")
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(SessionModel))
            sessions = result.scalars().all()
            if sessions:
                for session in sessions:
                    print(f"   - {session.name} (ID: {session.id}, User: {session.user_id}, Tenant: {session.tenant_id}, Status: {session.status})")
            else:
                print("   ⚠️  Nessuna sessione trovata nel database")
    except Exception as e:
        print(f"   ❌ Errore: {e}")
    
    # Verifica tenant di default
    print("\n5. Verifica tenant di default...")
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Tenant).where(Tenant.schema_name == "tenant_default")
            )
            default_tenant = result.scalar_one_or_none()
            if default_tenant:
                print(f"   ✅ Tenant di default trovato: {default_tenant.name} (ID: {default_tenant.id})")
            else:
                print("   ⚠️  Tenant di default non trovato (schema_name='tenant_default')")
    except Exception as e:
        print(f"   ❌ Errore: {e}")
    
    print("\n✅ Diagnostica completata")


if __name__ == "__main__":
    asyncio.run(diagnose())

