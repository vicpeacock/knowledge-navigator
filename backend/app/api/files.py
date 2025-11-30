from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import List, Optional
import shutil
from pathlib import Path

from app.db.database import get_db
from app.models.database import File as FileModel, Session as SessionModel
from app.models.schemas import File as FileSchema
from app.core.config import settings
from app.services.file_processor import FileProcessor
from app.services.embedding_service import EmbeddingService
from app.core.dependencies import get_memory_manager
from app.core.memory_manager import MemoryManager
from app.core.tenant_context import get_tenant_id
from app.core.user_context import get_current_user

router = APIRouter()
file_processor = FileProcessor()
embedding_service = EmbeddingService()


@router.post("/upload", response_model=FileSchema, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    session_id: Optional[UUID] = None,  # Optional: session where uploaded (for backward compatibility)
    db: AsyncSession = Depends(get_db),
    memory: MemoryManager = Depends(get_memory_manager),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user = Depends(get_current_user),
):
    """Upload and process a file for the current user (for current tenant)"""
    import logging
    logger = logging.getLogger(__name__)
    
    # If session_id provided, verify it belongs to user (optional, for backward compatibility)
    if session_id:
        result = await db.execute(
            select(SessionModel).where(
                SessionModel.id == session_id,
                SessionModel.tenant_id == tenant_id,
                SessionModel.user_id == current_user.id
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
    
    # Check file size
    file_content = await file.read()
    if len(file_content) > settings.max_file_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {settings.max_file_size} bytes",
        )
    
    # Save file in user-specific directory (not session-specific)
    user_dir = settings.upload_dir / "users" / str(current_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename to avoid conflicts
    import uuid as uuid_lib
    file_extension = Path(file.filename).suffix
    unique_filename = f"{uuid_lib.uuid4()}{file_extension}"
    filepath = user_dir / unique_filename
    
    with open(filepath, "wb") as f:
        f.write(file_content)
    
    # Process file
    file_data = file_processor.extract_text(str(filepath), file.content_type)
    
    # Create file record - file belongs to user, not session
    file_record = FileModel(
        user_id=current_user.id,  # File belongs to user
        session_id=session_id,  # Optional: session where uploaded
        tenant_id=tenant_id,
        filename=file.filename,  # Keep original filename
        filepath=str(filepath),
        mime_type=file.content_type,
        metadata=file_data["metadata"],
    )
    db.add(file_record)
    await db.commit()
    await db.refresh(file_record)
    
    # Generate embeddings and store in ChromaDB if text was extracted
    if file_data["text"]:
        try:
            embedding = embedding_service.generate_embedding(file_data["text"])
            embedding_id = f"file_{file_record.id}"
            
            # Truncate text if too long (ChromaDB has limits)
            text_content = file_data["text"]
            if len(text_content) > 20000:  # ChromaDB document limit
                text_content = text_content[:20000] + "... [truncated]"
            
            # Get tenant-specific collection
            file_collection = memory._get_collection("file_embeddings", tenant_id)
            file_collection.add(
                ids=[embedding_id],
                embeddings=[embedding],
                documents=[text_content],
                metadatas=[
                    {
                        "user_id": str(current_user.id),  # Store user_id instead of session_id
                        "file_id": str(file_record.id),
                        "filename": file.filename,
                        "session_id": str(session_id) if session_id else None,  # Optional: keep for backward compatibility
                    }
                ],
            )
            logger.info(f"File embedding stored: {file.filename}, user: {current_user.id}, text length: {len(file_data['text'])}")
        except Exception as e:
            logger.error(f"Error storing file embedding: {e}", exc_info=True)
            # Continue even if embedding fails
    else:
        logger.warning(f"No text extracted from file: {file.filename}")
    
    return FileSchema(
        id=file_record.id,
        user_id=file_record.user_id,
        session_id=file_record.session_id,
        filename=file_record.filename,
        filepath=file_record.filepath,
        mime_type=file_record.mime_type,
        uploaded_at=file_record.uploaded_at,
        metadata=file_record.session_metadata or {},
    )


@router.get("/", response_model=List[FileSchema])
async def get_user_files(
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user = Depends(get_current_user),
):
    """Get all files for the current user (for current tenant)"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"📁 Getting files for user {current_user.email}")
    
    try:
        result = await db.execute(
            select(FileModel)
            .where(
                FileModel.user_id == current_user.id,
                FileModel.tenant_id == tenant_id
            )
            .order_by(FileModel.uploaded_at.desc())
        )
        files = result.scalars().all()
        logger.info(f"   Found {len(files)} files for user {current_user.email}")
    except Exception as e:
        logger.error(f"   Error querying files: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving files: {str(e)}")
    
    return [
        FileSchema(
            id=f.id,
            user_id=f.user_id,
            session_id=f.session_id,
            filename=f.filename,
            filepath=f.filepath,
            mime_type=f.mime_type,
            uploaded_at=f.uploaded_at,
            metadata=f.session_metadata or {},
        )
        for f in files
    ]


@router.get("/session/{session_id}", response_model=List[FileSchema])
async def get_session_files(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user = Depends(get_current_user),
):
    """Get all files for a session (for current tenant and user) - DEPRECATED: returns user files"""
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"⚠️  get_session_files called - deprecated endpoint, using user files instead")
    
    # For backward compatibility, return user files (files are now user-scoped)
    return await get_user_files(db=db, tenant_id=tenant_id, current_user=current_user)


@router.get("/id/{file_id}", response_model=FileSchema)
async def get_file(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user = Depends(get_current_user),
):
    """Get a file by ID (for current tenant and user)"""
    result = await db.execute(
        select(FileModel).where(
            FileModel.id == file_id,
            FileModel.tenant_id == tenant_id,
            FileModel.user_id == current_user.id  # Verify ownership
        )
    )
    file = result.scalar_one_or_none()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Map session_metadata to metadata for response
    return FileSchema(
        id=file.id,
        user_id=file.user_id,
        session_id=file.session_id,
        filename=file.filename,
        filepath=file.filepath,
        mime_type=file.mime_type,
        uploaded_at=file.uploaded_at,
        metadata=file.session_metadata or {},
    )


@router.delete("/id/{file_id}", status_code=204)
async def delete_file(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    memory: MemoryManager = Depends(get_memory_manager),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user = Depends(get_current_user),
):
    """Delete a file (for current tenant and user - ownership required)"""
    result = await db.execute(
        select(FileModel).where(
            FileModel.id == file_id,
            FileModel.tenant_id == tenant_id,
            FileModel.user_id == current_user.id  # Verify ownership
        )
    )
    file = result.scalar_one_or_none()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Delete from ChromaDB - remove all embeddings for this file
    import logging
    logger = logging.getLogger(__name__)
    
    # Get tenant-specific collection
    file_collection = memory._get_collection("file_embeddings", tenant_id)
    
    embedding_id = f"file_{file_id}"
    deleted_from_chroma = False
    
    # First, check what embeddings exist for this file and delete them all
    embedding_ids_to_delete = []
    try:
        # Try to find embeddings by file_id in metadata
        existing_embeddings = file_collection.get(
            where={"file_id": str(file_id)}
        )
        embedding_ids_to_delete = existing_embeddings.get('ids', [])
        logger.info(f"Found {len(embedding_ids_to_delete)} embeddings for file_id {file_id}")
        if embedding_ids_to_delete:
            logger.info(f"Embedding IDs to delete: {embedding_ids_to_delete}")
    except Exception as e:
        logger.warning(f"Could not check existing embeddings by file_id: {e}")
        # Try alternative method
        try:
            existing_embeddings = file_collection.get(
                where={"session_id": str(file.session_id)}
            )
            # Filter by file_id in metadata manually
            all_ids = existing_embeddings.get('ids', [])
            all_metadatas = existing_embeddings.get('metadatas', [])
            for i, meta in enumerate(all_metadatas):
                if isinstance(meta, dict) and meta.get("file_id") == str(file_id):
                    if i < len(all_ids):
                        embedding_ids_to_delete.append(all_ids[i])
            logger.info(f"Found {len(embedding_ids_to_delete)} embeddings for file_id {file_id} (alternative method)")
        except Exception as e2:
            logger.warning(f"Could not check existing embeddings (alternative): {e2}")
    
    # Always add the standard embedding_id format
    embedding_ids_to_delete.append(embedding_id)
    # Remove duplicates
    embedding_ids_to_delete = list(set(embedding_ids_to_delete))
    
    deleted_from_chroma = False
    try:
        # Strategy 1: Delete all found IDs
        if embedding_ids_to_delete:
            try:
                result = file_collection.delete(ids=embedding_ids_to_delete)
                logger.info(f"Deleted {len(embedding_ids_to_delete)} file embeddings by IDs: {embedding_ids_to_delete}")
                deleted_from_chroma = True
            except Exception as e:
                logger.debug(f"Could not delete by IDs {embedding_ids_to_delete}: {e}")
        
        # Strategy 2: Delete by ID (standard format) - fallback if batch delete failed
        if not deleted_from_chroma:
            try:
                result = file_collection.delete(ids=[embedding_id])
                logger.info(f"Deleted file embedding by ID: {embedding_id}, result: {result}")
                deleted_from_chroma = True
            except Exception as e:
                logger.debug(f"Could not delete by ID {embedding_id}: {e}")
        
        # Strategy 3: Delete by file_id in metadata (more reliable - try all syntax variants)
        if not deleted_from_chroma:
            try:
                # ChromaDB where clause needs $eq operator for equality
                file_collection.delete(
                    where={"file_id": {"$eq": str(file_id)}}
                )
                logger.info(f"Deleted file embeddings by file_id metadata ($eq): {file_id}")
                deleted_from_chroma = True
            except Exception as e1:
                # Try with simple equality (older ChromaDB versions)
                try:
                    file_collection.delete(
                        where={"file_id": str(file_id)}
                    )
                    logger.info(f"Deleted file embeddings by file_id metadata (simple): {file_id}")
                    deleted_from_chroma = True
                except Exception as e2:
                    logger.debug(f"Could not delete by file_id metadata {file_id}: {e1}, {e2}")
        
        # Strategy 4: Delete by user_id and file_id combination (preferred method now)
        if not deleted_from_chroma:
            try:
                # ChromaDB where clause with multiple conditions
                file_collection.delete(
                    where={"$and": [{"user_id": {"$eq": str(file.user_id)}}, {"file_id": {"$eq": str(file_id)}}]}
                )
                logger.info(f"Deleted file embeddings by user_id and file_id ($and): {file.user_id}, {file_id}")
                deleted_from_chroma = True
            except Exception as e1:
                # Try with simple equality
                try:
                    file_collection.delete(
                        where={"user_id": str(file.user_id), "file_id": str(file_id)}
                    )
                    logger.info(f"Deleted file embeddings by user_id and file_id (simple): {file.user_id}, {file_id}")
                    deleted_from_chroma = True
                except Exception as e2:
                    logger.debug(f"Could not delete by user_id and file_id: {e1}, {e2}")
        
        # Strategy 5: Delete by session_id and file_id combination (backward compatibility)
        if not deleted_from_chroma and file.session_id:
            try:
                # ChromaDB where clause with multiple conditions
                file_collection.delete(
                    where={"$and": [{"session_id": {"$eq": str(file.session_id)}}, {"file_id": {"$eq": str(file_id)}}]}
                )
                logger.info(f"Deleted file embeddings by session_id and file_id ($and): {file.session_id}, {file_id}")
                deleted_from_chroma = True
            except Exception as e1:
                # Try with simple equality
                try:
                    file_collection.delete(
                        where={"session_id": str(file.session_id), "file_id": str(file_id)}
                    )
                    logger.info(f"Deleted file embeddings by session_id and file_id (simple): {file.session_id}, {file_id}")
                    deleted_from_chroma = True
                except Exception as e2:
                    logger.debug(f"Could not delete by session_id and file_id: {e1}, {e2}")
        
        if not deleted_from_chroma:
            logger.error(f"Failed to delete file embedding from ChromaDB for file {file_id}. Embedding may still exist in RAG.")
    except Exception as e:
        logger.error(f"Error deleting file embedding from ChromaDB: {e}", exc_info=True)
        # Continue with file deletion even if ChromaDB deletion fails
    
    # Delete physical file
    if Path(file.filepath).exists():
        Path(file.filepath).unlink()
    
    # Delete from database
    await db.delete(file)
    await db.commit()
    return None


@router.post("/cleanup-orphans", status_code=200)
async def cleanup_orphan_embeddings(
    db: AsyncSession = Depends(get_db),
    memory: MemoryManager = Depends(get_memory_manager),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """Clean up orphaned embeddings (embeddings that point to files that no longer exist)"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Get tenant-specific collection
        file_collection = memory._get_collection("file_embeddings", tenant_id)
        
        # Get all embeddings from ChromaDB (for this tenant)
        all_embeddings = file_collection.get()
        embedding_ids = all_embeddings.get('ids', [])
        metadatas = all_embeddings.get('metadatas', [])
        
        if not embedding_ids:
            return {
                "message": "No embeddings found in ChromaDB",
                "total": 0,
                "orphaned": 0,
                "deleted": 0
            }
        
        # Get all file IDs from database (filtered by tenant)
        result = await db.execute(
            select(FileModel.id).where(FileModel.tenant_id == tenant_id)
        )
        existing_file_ids = {str(fid) for fid in result.scalars().all()}
        
        # Find orphaned embeddings
        orphaned_ids = []
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
            
            if file_id and str(file_id) not in existing_file_ids:
                orphaned_ids.append(embedding_id)
        
        # Delete orphaned embeddings
        deleted_count = 0
        if orphaned_ids:
            # Delete in batches
            batch_size = 100
            for i in range(0, len(orphaned_ids), batch_size):
                batch = orphaned_ids[i:i + batch_size]
                file_collection.delete(ids=batch)
                deleted_count += len(batch)
                logger.info(f"Deleted batch {i//batch_size + 1}: {len(batch)} orphaned embeddings")
        
        return {
            "message": f"Cleanup complete",
            "total": len(embedding_ids),
            "orphaned": len(orphaned_ids),
            "deleted": deleted_count,
            "remaining": len(embedding_ids) - deleted_count
        }
    except Exception as e:
        logger.error(f"Error cleaning up orphaned embeddings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error cleaning up orphaned embeddings: {str(e)}")


@router.post("/search")
async def search_files(
    query: str,
    n_results: int = 5,
    db: AsyncSession = Depends(get_db),
    memory: MemoryManager = Depends(get_memory_manager),
    tenant_id: UUID = Depends(get_tenant_id),
    current_user = Depends(get_current_user),
):
    """Search user files using semantic search (for current tenant and user)"""
    # Get tenant-specific collection
    file_collection = memory._get_collection("file_embeddings", tenant_id)
    
    query_embedding = embedding_service.generate_embedding(query)
    
    results = file_collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where={"user_id": str(current_user.id)},  # Files are user-scoped now
    )
    
    file_ids = [
        metadata.get("file_id")
        for metadata in results.get("metadatas", [[]])[0]
    ]
    
    # Get file records (filtered by tenant)
    files = []
    if file_ids:
        result = await db.execute(
            select(FileModel).where(
                FileModel.id.in_(file_ids),
                FileModel.tenant_id == tenant_id
            )
        )
        files = result.scalars().all()
    
    return {
        "query": query,
        "results": [
            {
                "file": FileSchema.model_validate(f),
                "relevance_score": 1.0,  # Could calculate actual similarity
            }
            for f in files
        ],
    }

