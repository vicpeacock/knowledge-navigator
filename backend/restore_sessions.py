#!/usr/bin/env python3
"""Check and restore sessions status"""
import asyncio
from app.db.database import get_db
from app.models.database import Session
from sqlalchemy import select, update

async def restore():
    async for db in get_db():
        # Check all sessions
        result = await db.execute(select(Session))
        sessions = result.scalars().all()
        print(f'\nTotal sessions in DB: {len(sessions)}')
        
        if not sessions:
            print("No sessions found in database")
            return
        
        # Count by status
        active = [s for s in sessions if s.status == 'active']
        archived = [s for s in sessions if s.status == 'archived']
        deleted = [s for s in sessions if s.status == 'deleted']
        
        print(f'Active: {len(active)}')
        print(f'Archived: {len(archived)}')
        print(f'Deleted: {len(deleted)}')
        
        # If there are deleted sessions, restore them to active
        if deleted:
            print(f'\nRestoring {len(deleted)} deleted sessions to active...')
            for s in deleted:
                print(f'  - Restoring: {s.id} | {s.name}')
                await db.execute(
                    update(Session)
                    .where(Session.id == s.id)
                    .values(status='active')
                )
            await db.commit()
            print('✅ Sessions restored')
        
        # Show all sessions
        print(f'\nAll sessions after restore:')
        result = await db.execute(select(Session).order_by(Session.updated_at.desc()))
        all_sessions = result.scalars().all()
        for s in all_sessions:
            print(f'  - {s.id} | {s.name} | status: {s.status}')
        
        break

if __name__ == '__main__':
    asyncio.run(restore())

