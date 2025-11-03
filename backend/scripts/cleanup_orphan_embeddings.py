#!/usr/bin/env python3
"""
Script to clean up orphaned file embeddings from ChromaDB.
Removes embeddings that point to files that no longer exist in the database.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.database import File as FileModel
from app.core.memory_manager import MemoryManager
import chromadb
from chromadb.config import Settings as ChromaSettings

async def cleanup_orphan_embeddings():
    """Remove all embeddings that point to files that don't exist anymore"""
    
    print("🔍 Starting cleanup of orphaned embeddings...")
    
    # Initialize database connection
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    # Initialize ChromaDB client
    chroma_client = chromadb.HttpClient(
        host=settings.chromadb_host,
        port=settings.chromadb_port,
    )
    
    file_embeddings_collection = chroma_client.get_or_create_collection(
        name="file_embeddings",
        metadata={"hnsw:space": "cosine"},
    )
    
    # Get all embeddings from ChromaDB
    print("\n📊 Fetching all embeddings from ChromaDB...")
    all_embeddings = file_embeddings_collection.get()
    
    embedding_ids = all_embeddings.get('ids', [])
    metadatas = all_embeddings.get('metadatas', [])
    
    print(f"Found {len(embedding_ids)} total embeddings in ChromaDB")
    
    if not embedding_ids:
        print("✅ No embeddings found. Nothing to clean up.")
        return
    
    # Get all file IDs from database
    print("\n📊 Fetching all file IDs from database...")
    async with async_session() as db:
        result = await db.execute(select(FileModel.id))
        existing_file_ids = {str(fid) for fid in result.scalars().all()}
        print(f"Found {len(existing_file_ids)} files in database: {existing_file_ids}")
    
    # Find orphaned embeddings
    orphaned_ids = []
    valid_ids = []
    
    print("\n🔍 Checking which embeddings are orphaned...")
    for i, embedding_id in enumerate(embedding_ids):
        metadata = metadatas[i] if i < len(metadatas) else {}
        
        file_id = None
        if isinstance(metadata, dict):
            file_id = metadata.get("file_id")
        elif metadata is not None:
            try:
                if hasattr(metadata, 'get'):
                    file_id = metadata.get("file_id")
                elif hasattr(metadata, '__dict__'):
                    file_id = getattr(metadata, 'file_id', None)
            except:
                pass
        
        if file_id:
            if str(file_id) in existing_file_ids:
                valid_ids.append(embedding_id)
            else:
                orphaned_ids.append(embedding_id)
                print(f"  ❌ Orphaned: {embedding_id} -> file_id {file_id} (not in database)")
        else:
            # If no file_id in metadata, it's suspicious - keep for now but log
            print(f"  ⚠️  Warning: {embedding_id} has no file_id in metadata")
            valid_ids.append(embedding_id)  # Keep it for safety
    
    print(f"\n📈 Summary:")
    print(f"  Total embeddings: {len(embedding_ids)}")
    print(f"  Valid embeddings: {len(valid_ids)}")
    print(f"  Orphaned embeddings: {len(orphaned_ids)}")
    
    if not orphaned_ids:
        print("\n✅ No orphaned embeddings found. Nothing to clean up!")
        return
    
    # Delete orphaned embeddings
    print(f"\n🗑️  Deleting {len(orphaned_ids)} orphaned embeddings...")
    
    try:
        # Delete in batches to avoid overwhelming ChromaDB
        batch_size = 100
        deleted_count = 0
        
        for i in range(0, len(orphaned_ids), batch_size):
            batch = orphaned_ids[i:i + batch_size]
            file_embeddings_collection.delete(ids=batch)
            deleted_count += len(batch)
            print(f"  Deleted batch {i//batch_size + 1}: {len(batch)} embeddings ({deleted_count}/{len(orphaned_ids)})")
        
        print(f"\n✅ Successfully deleted {deleted_count} orphaned embeddings!")
        
        # Verify deletion
        remaining_embeddings = file_embeddings_collection.get()
        print(f"\n📊 Verification: {len(remaining_embeddings.get('ids', []))} embeddings remaining in ChromaDB")
        
    except Exception as e:
        print(f"\n❌ Error deleting orphaned embeddings: {e}")
        import traceback
        traceback.print_exc()
        raise
    
    print("\n✨ Cleanup complete!")

if __name__ == "__main__":
    asyncio.run(cleanup_orphan_embeddings())

