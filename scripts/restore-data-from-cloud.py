#!/usr/bin/env python3
"""
Script per recuperare dati dal database Supabase (Cloud) e ripristinarli nel database locale.
"""
import os
import sys
import asyncio
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
import asyncpg
from typing import Optional

# Aggiungi il path del backend
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

async def export_from_cloud(source_db_url: str) -> dict:
    """Esporta dati dal database cloud"""
    print(f"📥 Connessione al database cloud...")
    print(f"   URL: {source_db_url.split('@')[1] if '@' in source_db_url else 'hidden'}")
    
    # Connessione cloud con timeout e retry
    cloud_engine = create_async_engine(
        source_db_url, 
        echo=False,
        pool_pre_ping=True,
        connect_args={
            "server_settings": {
                "application_name": "knowledge_navigator_restore"
            },
            "timeout": 30,
            "command_timeout": 60,
        }
    )
    
    data = {
        "tenants": [],
        "users": [],
        "sessions": [],
        "messages": [],
        "integrations": [],
        "files": [],
    }
    
    async with cloud_engine.connect() as conn:
        # Export tenants
        print("📦 Esportazione tenants...")
        result = await conn.execute(text("SELECT * FROM tenants ORDER BY created_at"))
        for row in result:
            data["tenants"].append(dict(row._mapping))
        print(f"   ✅ {len(data['tenants'])} tenants esportati")
        
        # Export users
        print("👥 Esportazione users...")
        result = await conn.execute(text("SELECT * FROM users ORDER BY created_at"))
        for row in result:
            # Rimuovi None values per evitare problemi
            user_dict = {k: v for k, v in dict(row._mapping).items() if v is not None}
            data["users"].append(user_dict)
        print(f"   ✅ {len(data['users'])} users esportati")
        
        # Export sessions
        print("💬 Esportazione sessions...")
        result = await conn.execute(text("SELECT * FROM sessions ORDER BY created_at"))
        for row in result:
            data["sessions"].append(dict(row._mapping))
        print(f"   ✅ {len(data['sessions'])} sessions esportate")
        
        # Export messages
        print("📨 Esportazione messages...")
        result = await conn.execute(text("SELECT * FROM messages ORDER BY created_at"))
        for row in result:
            data["messages"].append(dict(row._mapping))
        print(f"   ✅ {len(data['messages'])} messages esportati")
        
        # Export integrations
        print("🔗 Esportazione integrations...")
        result = await conn.execute(text("SELECT * FROM integrations ORDER BY created_at"))
        for row in result:
            data["integrations"].append(dict(row._mapping))
        print(f"   ✅ {len(data['integrations'])} integrations esportate")
        
        # Export files
        print("📁 Esportazione files...")
        result = await conn.execute(text("SELECT * FROM files ORDER BY uploaded_at"))
        for row in result:
            data["files"].append(dict(row._mapping))
        print(f"   ✅ {len(data['files'])} files esportati")
    
    await cloud_engine.dispose()
    
    return data

async def import_to_local(target_db_url: str, data: dict):
    """Importa dati nel database locale"""
    print(f"\n📤 Importazione nel database locale...")
    
    local_engine = create_async_engine(target_db_url, echo=False)
    
    async with local_engine.begin() as conn:
        # Import tenants
        if data["tenants"]:
            print(f"📦 Importazione {len(data['tenants'])} tenants...")
            for tenant in data["tenants"]:
                await conn.execute(
                    text("""
                        INSERT INTO tenants (id, name, created_at, metadata)
                        VALUES (:id, :name, :created_at, :metadata)
                        ON CONFLICT (id) DO NOTHING
                    """),
                    tenant
                )
            print(f"   ✅ Tenants importati")
        
        # Import users
        if data["users"]:
            print(f"👥 Importazione {len(data['users'])} users...")
            for user in data["users"]:
                # Rimuovi campi che potrebbero causare problemi
                user_clean = {k: v for k, v in user.items() if v is not None}
                columns = ", ".join(user_clean.keys())
                placeholders = ", ".join([f":{k}" for k in user_clean.keys()])
                values_expr = ", ".join([f"EXCLUDED.{k}" for k in user_clean.keys() if k != "id"])
                conflict = ", ".join([f"{k} = EXCLUDED.{k}" for k in user_clean.keys() if k != "id" and k != "created_at"])
                
                await conn.execute(
                    text(f"""
                        INSERT INTO users ({columns})
                        VALUES ({placeholders})
                        ON CONFLICT (id) DO UPDATE SET {conflict}
                    """),
                    user_clean
                )
            print(f"   ✅ Users importati")
        
        # Import sessions
        if data["sessions"]:
            print(f"💬 Importazione {len(data['sessions'])} sessions...")
            for session in data["sessions"]:
                session_clean = {k: v for k, v in session.items() if v is not None}
                columns = ", ".join(session_clean.keys())
                placeholders = ", ".join([f":{k}" for k in session_clean.keys()])
                await conn.execute(
                    text(f"""
                        INSERT INTO sessions ({columns})
                        VALUES ({placeholders})
                        ON CONFLICT (id) DO NOTHING
                    """),
                    session_clean
                )
            print(f"   ✅ Sessions importate")
        
        # Import messages
        if data["messages"]:
            print(f"📨 Importazione {len(data['messages'])} messages...")
            # Import in batch per performance
            batch_size = 100
            for i in range(0, len(data["messages"]), batch_size):
                batch = data["messages"][i:i+batch_size]
                for msg in batch:
                    msg_clean = {k: v for k, v in msg.items() if v is not None}
                    columns = ", ".join(msg_clean.keys())
                    placeholders = ", ".join([f":{k}" for k in msg_clean.keys()])
                    await conn.execute(
                        text(f"""
                            INSERT INTO messages ({columns})
                            VALUES ({placeholders})
                            ON CONFLICT (id) DO NOTHING
                        """),
                        msg_clean
                    )
            print(f"   ✅ Messages importati")
        
        # Import integrations
        if data["integrations"]:
            print(f"🔗 Importazione {len(data['integrations'])} integrations...")
            for integration in data["integrations"]:
                int_clean = {k: v for k, v in integration.items() if v is not None}
                columns = ", ".join(int_clean.keys())
                placeholders = ", ".join([f":{k}" for k in int_clean.keys()])
                await conn.execute(
                    text(f"""
                        INSERT INTO integrations ({columns})
                        VALUES ({placeholders})
                        ON CONFLICT (id) DO NOTHING
                    """),
                    int_clean
                )
            print(f"   ✅ Integrations importate")
        
        # Import files (solo metadati, non i file fisici)
        if data["files"]:
            print(f"📁 Importazione {len(data['files'])} file metadata...")
            for file in data["files"]:
                file_clean = {k: v for k, v in file.items() if v is not None}
                columns = ", ".join(file_clean.keys())
                placeholders = ", ".join([f":{k}" for k in file_clean.keys()])
                await conn.execute(
                    text(f"""
                        INSERT INTO files ({columns})
                        VALUES ({placeholders})
                        ON CONFLICT (id) DO NOTHING
                    """),
                    file_clean
                )
            print(f"   ✅ File metadata importati")
    
    await local_engine.dispose()
    print("\n✅ Importazione completata!")

async def main():
    # Database cloud (Supabase) - URL encoding della password
    cloud_url_env = os.getenv("CLOUD_DATABASE_URL")
    if cloud_url_env:
        cloud_url = cloud_url_env
    else:
        # Password ha caratteri speciali, usiamo URL encoding
        from urllib.parse import quote_plus
        password = "PllVcn_66.superbase"
        encoded_password = quote_plus(password)
        # Prova anche con connessione diretta usando pooler
        # Formato: postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres
        cloud_url = f"postgresql+asyncpg://postgres:{encoded_password}@db.zdyuqekimdpsmnelzvri.supabase.co:5432/postgres"
        print(f"⚠️  Usando connection string costruita manualmente")
        print(f"   Se fallisce, verifica la connessione di rete a Supabase")
    
    # Database locale
    local_url = os.getenv("LOCAL_DATABASE_URL") or "postgresql+asyncpg://knavigator:knavigator_pass@localhost:5432/knowledge_navigator"
    
    print("🔄 Restore dati dal Cloud al database locale")
    print("=" * 60)
    
    # Export da cloud
    data = await export_from_cloud(cloud_url)
    
    # Import in locale
    await import_to_local(local_url, data)
    
    print("\n✅ Restore completato!")
    print(f"   - {len(data['users'])} users ripristinati")
    print(f"   - {len(data['sessions'])} sessions ripristinate")
    print(f"   - {len(data['messages'])} messages ripristinati")

if __name__ == "__main__":
    asyncio.run(main())

