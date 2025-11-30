#!/usr/bin/env python3
"""
Script per importare i dati esportati da Cloud Run nel database locale
"""
import json
import sys
from pathlib import Path
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from uuid import UUID

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

LOCAL_DB_URL = "postgresql+asyncpg://knavigator:knavigator_pass@localhost:5432/knowledge_navigator"

def parse_datetime(value):
    """Converte una stringa ISO in datetime"""
    if isinstance(value, str):
        try:
            # Rimuovi il timezone se presente e converti
            if value.endswith('+00:00') or value.endswith('Z'):
                value = value.replace('+00:00', '').replace('Z', '')
            return datetime.fromisoformat(value)
        except:
            return None
    return value

async def import_users(db: AsyncSession, users: list):
    """Importa users nel database locale"""
    print(f"👥 Importazione {len(users)} users...")
    
    # Recupera il tenant_id di default
    tenant_result = await db.execute(text("SELECT id FROM tenants WHERE schema_name = 'tenant_default' LIMIT 1"))
    default_tenant = tenant_result.scalar_one_or_none()
    if not default_tenant:
        print("   ❌ Tenant di default non trovato. Esegui le migrazioni prima.")
        return
    tenant_id = default_tenant
    
    success_count = 0
    for user in users:
        try:
            # Pulisci i dati e converti le date
            user_clean = {}
            for k, v in user.items():
                if v is None:
                    continue
                # Converti date ISO in datetime
                if k in ('created_at', 'last_login_at', 'password_reset_expires'):
                    user_clean[k] = parse_datetime(v)
                else:
                    user_clean[k] = v
            
            # Aggiungi tenant_id se mancante
            if 'tenant_id' not in user_clean:
                user_clean['tenant_id'] = tenant_id
            
            # Costruisci query dinamica
            columns = ", ".join(user_clean.keys())
            placeholders = ", ".join([f":{k}" for k in user_clean.keys()])
            updates = ", ".join([f"{k} = EXCLUDED.{k}" for k in user_clean.keys() if k != "id" and k != "created_at"])
            
            query = f"""
                INSERT INTO users ({columns})
                VALUES ({placeholders})
                ON CONFLICT (id) DO UPDATE SET {updates}
            """
            await db.execute(text(query), user_clean)
            await db.commit()
            success_count += 1
        except Exception as e:
            await db.rollback()
            print(f"   ⚠️  Errore importazione user {user.get('email', 'unknown')}: {e}")
    
    print(f"   ✅ {success_count}/{len(users)} users importati")

async def import_sessions(db: AsyncSession, sessions: list):
    """Importa sessions nel database locale"""
    print(f"💬 Importazione {len(sessions)} sessions...")
    for session in sessions:
        try:
            # Pulisci i dati e converti le date
            session_clean = {}
            for k, v in session.items():
                if v is None:
                    continue
                # Converti date ISO in datetime
                if k in ('created_at', 'updated_at', 'archived_at'):
                    session_clean[k] = parse_datetime(v)
                else:
                    session_clean[k] = v
            
            columns = ", ".join(session_clean.keys())
            placeholders = ", ".join([f":{k}" for k in session_clean.keys()])
            
            query = f"""
                INSERT INTO sessions ({columns})
                VALUES ({placeholders})
                ON CONFLICT (id) DO NOTHING
            """
            await db.execute(text(query), session_clean)
        except Exception as e:
            print(f"   ⚠️  Errore importazione session {session.get('id', 'unknown')}: {e}")
    
    await db.commit()
    print(f"   ✅ Sessions importate")

async def main():
    # Leggi dati esportati
    users_file = Path("/tmp/cloud_users.json")
    sessions_file = Path("/tmp/cloud_sessions.json")
    
    if not users_file.exists() and not sessions_file.exists():
        print("❌ Nessun file di export trovato in /tmp/")
        print("   Esegui prima: ./scripts/export-from-cloud-run.sh")
        sys.exit(1)
    
    users = []
    sessions = []
    
    if users_file.exists():
        with open(users_file) as f:
            users = json.load(f)
    
    if sessions_file.exists():
        with open(sessions_file) as f:
            sessions_data = json.load(f)
            # Se è una lista, usala; altrimenti è un errore (es. {"detail":"Not Found"})
            if isinstance(sessions_data, list):
                sessions = sessions_data
            else:
                print(f"   ⚠️  Sessions file non contiene una lista valida: {sessions_data}")
                sessions = []
    
    print(f"📥 Importazione dati nel database locale")
    print(f"   - {len(users)} users")
    print(f"   - {len(sessions)} sessions")
    print("")
    
    # Connessione al database locale
    engine = create_async_engine(LOCAL_DB_URL, echo=False)
    
    async with engine.begin() as conn:
        db = AsyncSession(conn)
        
        if users:
            await import_users(db, users)
        
        if sessions:
            await import_sessions(db, sessions)
    
    await engine.dispose()
    
    print("\n✅ Importazione completata!")

if __name__ == "__main__":
    asyncio.run(main())

