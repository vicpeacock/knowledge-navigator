#!/usr/bin/env python3
"""Script per verificare le sessioni nel database"""
import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.database import get_db
from app.models.database import Session
from sqlalchemy import select

async def check_sessions():
    try:
        async for db in get_db():
            result = await db.execute(select(Session))
            sessions = result.scalars().all()

            print(f"\n✅ Trovate {len(sessions)} sessioni nel database:\n")

            for s in sessions:
                print(f"  - ID: {s.id}")
                print(f"    Nome: {s.name}")
                print(f"    Titolo: {s.title or 'N/A'}")
                print(f"    Stato: {s.status}")
                print(f"    Creata: {s.created_at}")
                print(f"    Aggiornata: {s.updated_at}")
                print()

            # Count by status
            active = [s for s in sessions if s.status == 'active']
            archived = [s for s in sessions if s.status == 'archived']

            print(f"\n📊 Riepilogo:")
            print(f"  - Attive: {len(active)}")
            print(f"  - Archiviate: {len(archived)}")

            break
    except Exception as e:
        print(f"❌ Errore: {e}")
        import traceback
        traceback.print_exc()


def main() -> None:
    asyncio.run(check_sessions())


if __name__ == "__main__":
    main()

