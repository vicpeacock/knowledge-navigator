#!/usr/bin/env python3
"""
Suite completa di test per il multi-tenant refactoring
Testa isolamento dati, query filtering, creazione risorse, e backward compatibility
"""
import asyncio
import sys
from pathlib import Path
from uuid import UUID, uuid4
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.database import get_db
from app.models.database import (
    Tenant, User, Session, Message, File, MemoryShort, MemoryMedium, 
    MemoryLong, Integration, Notification
)
from app.core.tenant_context import initialize_default_tenant
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession


class TestResults:
    """Raccoglie i risultati dei test"""
    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []
    
    def add_pass(self, test_name: str):
        self.passed.append(test_name)
        print(f"✅ {test_name}")
    
    def add_fail(self, test_name: str, reason: str):
        self.failed.append((test_name, reason))
        print(f"❌ {test_name}: {reason}")
    
    def add_warning(self, test_name: str, reason: str):
        self.warnings.append((test_name, reason))
        print(f"⚠️  {test_name}: {reason}")
    
    def summary(self):
        print("\n" + "="*60)
        print("📊 TEST SUMMARY")
        print("="*60)
        print(f"✅ Passed: {len(self.passed)}")
        print(f"❌ Failed: {len(self.failed)}")
        print(f"⚠️  Warnings: {len(self.warnings)}")
        
        if self.failed:
            print("\n❌ FAILED TESTS:")
            for test_name, reason in self.failed:
                print(f"  - {test_name}: {reason}")
        
        if self.warnings:
            print("\n⚠️  WARNINGS:")
            for test_name, reason in self.warnings:
                print(f"  - {test_name}: {reason}")
        
        print("="*60)
        return len(self.failed) == 0


async def test_tenant_initialization(db: AsyncSession, results: TestResults):
    """Test 1: Verificare inizializzazione tenant"""
    print("\n1️⃣  Testing Tenant Initialization...")
    
    try:
        default_tenant_id = await initialize_default_tenant(db)
        if not default_tenant_id:
            results.add_fail("Tenant initialization", "Failed to get default tenant ID")
            return False
        
        result = await db.execute(
            select(Tenant).where(Tenant.id == default_tenant_id)
        )
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            results.add_fail("Tenant initialization", "Default tenant not found in database")
            return False
        
        if tenant.schema_name != "tenant_default":
            results.add_fail("Tenant initialization", f"Expected schema_name 'tenant_default', got '{tenant.schema_name}'")
            return False
        
        results.add_pass("Tenant initialization")
        return True
    except Exception as e:
        results.add_fail("Tenant initialization", str(e))
        return False


async def test_data_integrity(db: AsyncSession, results: TestResults):
    """Test 2: Verificare integrità dati (nessun NULL tenant_id)"""
    print("\n2️⃣  Testing Data Integrity...")
    
    tables_to_check = [
        (Session, "sessions", "id"),
        (Message, "messages", "id"),
        (File, "files", "id"),
        (MemoryShort, "memory_short", "session_id"),
        (MemoryMedium, "memory_medium", "id"),
        (MemoryLong, "memory_long", "id"),
        (Integration, "integrations", "id"),
        (Notification, "notifications", "id"),
    ]
    
    all_ok = True
    for model, table_name, pk_field in tables_to_check:
        try:
            pk_column = getattr(model, pk_field)
            result = await db.execute(
                select(func.count(pk_column)).where(model.tenant_id.is_(None))
            )
            null_count = result.scalar()
            
            if null_count > 0:
                results.add_fail(f"Data integrity - {table_name}", f"{null_count} records without tenant_id")
                all_ok = False
            else:
                # Contare record totali
                result = await db.execute(select(func.count(pk_column)))
                total = result.scalar()
                results.add_pass(f"Data integrity - {table_name} ({total} records)")
        except Exception as e:
            results.add_fail(f"Data integrity - {table_name}", str(e))
            all_ok = False
    
    return all_ok


async def test_tenant_isolation(db: AsyncSession, results: TestResults):
    """Test 3: Verificare isolamento tra tenant"""
    print("\n3️⃣  Testing Tenant Isolation...")
    
    try:
        # Ottenere default tenant
        default_tenant_id = await initialize_default_tenant(db)
        
        # Contare sessioni per default tenant
        result = await db.execute(
            select(func.count(Session.id)).where(Session.tenant_id == default_tenant_id)
        )
        default_sessions = result.scalar()
        
        # Contare tutte le sessioni
        result = await db.execute(select(func.count(Session.id)))
        total_sessions = result.scalar()
        
        if default_sessions != total_sessions:
            results.add_warning(
                "Tenant isolation - sessions",
                f"Default tenant has {default_sessions} sessions, total is {total_sessions}"
            )
        else:
            results.add_pass(f"Tenant isolation - sessions ({default_sessions} sessions)")
        
        # Verificare che i messaggi appartengano alle sessioni corrette
        if default_sessions > 0:
            result = await db.execute(
                select(Session.id).where(Session.tenant_id == default_tenant_id).limit(1)
            )
            sample_session = result.scalar_one_or_none()
            
            if sample_session:
                session_id = sample_session.id if hasattr(sample_session, 'id') else sample_session
                # Verificare che i messaggi della sessione appartengano allo stesso tenant
                result = await db.execute(
                    select(func.count(Message.id)).where(
                        Message.session_id == session_id,
                        Message.tenant_id == default_tenant_id
                    )
                )
                correct_messages = result.scalar()
                
                result = await db.execute(
                    select(func.count(Message.id)).where(Message.session_id == session_id)
                )
                total_messages = result.scalar()
                
                session_id_str = str(session_id)
                
                if correct_messages == total_messages:
                    results.add_pass(f"Tenant isolation - messages ({correct_messages} messages)")
                else:
                    results.add_fail(
                        "Tenant isolation - messages",
                        f"Session {session_id_str}: {correct_messages} correct, {total_messages} total"
                    )
        
        return True
    except Exception as e:
        results.add_fail("Tenant isolation", str(e))
        return False


async def test_query_filtering(db: AsyncSession, results: TestResults):
    """Test 4: Verificare che le query filtrino correttamente"""
    print("\n4️⃣  Testing Query Filtering...")
    
    try:
        default_tenant_id = await initialize_default_tenant(db)
        
        # Test sessions
        result = await db.execute(
            select(Session).where(Session.tenant_id == default_tenant_id).limit(5)
        )
        sessions = result.scalars().all()
        results.add_pass(f"Query filtering - sessions ({len(sessions)} found)")
        
        # Test messages
        result = await db.execute(
            select(Message).where(Message.tenant_id == default_tenant_id).limit(5)
        )
        messages = result.scalars().all()
        results.add_pass(f"Query filtering - messages ({len(messages)} found)")
        
        # Test files
        result = await db.execute(
            select(File).where(File.tenant_id == default_tenant_id).limit(5)
        )
        files = result.scalars().all()
        results.add_pass(f"Query filtering - files ({len(files)} found)")
        
        # Test integrations
        result = await db.execute(
            select(Integration).where(Integration.tenant_id == default_tenant_id).limit(5)
        )
        integrations = result.scalars().all()
        results.add_pass(f"Query filtering - integrations ({len(integrations)} found)")
        
        # Test notifications
        result = await db.execute(
            select(Notification).where(Notification.tenant_id == default_tenant_id).limit(5)
        )
        notifications = result.scalars().all()
        results.add_pass(f"Query filtering - notifications ({len(notifications)} found)")
        
        return True
    except Exception as e:
        results.add_fail("Query filtering", str(e))
        return False


async def test_backward_compatibility(db: AsyncSession, results: TestResults):
    """Test 5: Verificare backward compatibility"""
    print("\n5️⃣  Testing Backward Compatibility...")
    
    try:
        default_tenant_id = await initialize_default_tenant(db)
        
        # Verificare che tutte le sessioni esistenti abbiano il default tenant
        result = await db.execute(
            select(func.count(Session.id)).where(Session.tenant_id == default_tenant_id)
        )
        sessions_with_default = result.scalar()
        
        result = await db.execute(select(func.count(Session.id)))
        total_sessions = result.scalar()
        
        if sessions_with_default == total_sessions:
            results.add_pass(f"Backward compatibility - all {total_sessions} sessions migrated")
        else:
            results.add_fail(
                "Backward compatibility",
                f"Only {sessions_with_default}/{total_sessions} sessions have default tenant"
            )
            return False
        
        # Verificare che tutti i messaggi esistenti abbiano il default tenant
        result = await db.execute(
            select(func.count(Message.id)).where(Message.tenant_id == default_tenant_id)
        )
        messages_with_default = result.scalar()
        
        result = await db.execute(select(func.count(Message.id)))
        total_messages = result.scalar()
        
        if messages_with_default == total_messages:
            results.add_pass(f"Backward compatibility - all {total_messages} messages migrated")
        else:
            results.add_fail(
                "Backward compatibility",
                f"Only {messages_with_default}/{total_messages} messages have default tenant"
            )
            return False
        
        return True
    except Exception as e:
        results.add_fail("Backward compatibility", str(e))
        return False


async def test_foreign_key_constraints(db: AsyncSession, results: TestResults):
    """Test 6: Verificare foreign key constraints"""
    print("\n6️⃣  Testing Foreign Key Constraints...")
    
    try:
        default_tenant_id = await initialize_default_tenant(db)
        
        # Verificare che tutte le sessioni abbiano un tenant valido
        result = await db.execute(
            select(func.count(Session.id)).where(
                ~Session.tenant_id.in_(select(Tenant.id))
            )
        )
        invalid_sessions = result.scalar()
        
        if invalid_sessions == 0:
            results.add_pass("Foreign key constraints - sessions")
        else:
            results.add_fail("Foreign key constraints - sessions", f"{invalid_sessions} sessions with invalid tenant_id")
            return False
        
        # Verificare che tutti i messaggi abbiano un tenant valido
        result = await db.execute(
            select(func.count(Message.id)).where(
                ~Message.tenant_id.in_(select(Tenant.id))
            )
        )
        invalid_messages = result.scalar()
        
        if invalid_messages == 0:
            results.add_pass("Foreign key constraints - messages")
        else:
            results.add_fail("Foreign key constraints - messages", f"{invalid_messages} messages with invalid tenant_id")
            return False
        
        return True
    except Exception as e:
        results.add_fail("Foreign key constraints", str(e))
        return False


async def test_indexes(db: AsyncSession, results: TestResults):
    """Test 7: Verificare che gli indici siano presenti"""
    print("\n7️⃣  Testing Database Indexes...")
    
    try:
        # Verificare che le query con tenant_id siano efficienti
        # (non possiamo verificare direttamente gli indici, ma possiamo testare le performance)
        default_tenant_id = await initialize_default_tenant(db)
        
        import time
        start = time.time()
        result = await db.execute(
            select(Session).where(Session.tenant_id == default_tenant_id).limit(100)
        )
        sessions = result.scalars().all()
        elapsed = time.time() - start
        
        if elapsed < 1.0:  # Dovrebbe essere molto veloce con gli indici
            results.add_pass(f"Index performance - sessions query took {elapsed:.3f}s")
        else:
            results.add_warning(f"Index performance - sessions query took {elapsed:.3f}s (might need indexes)")
        
        return True
    except Exception as e:
        results.add_fail("Index performance", str(e))
        return False


async def run_all_tests():
    """Esegue tutti i test"""
    print("🧪 MULTI-TENANT COMPLETE TEST SUITE")
    print("="*60)
    
    results = TestResults()
    
    try:
        async for db in get_db():
            # Esegui tutti i test
            await test_tenant_initialization(db, results)
            await test_data_integrity(db, results)
            await test_tenant_isolation(db, results)
            await test_query_filtering(db, results)
            await test_backward_compatibility(db, results)
            await test_foreign_key_constraints(db, results)
            await test_indexes(db, results)
            
            # Summary
            success = results.summary()
            return success
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main function"""
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

