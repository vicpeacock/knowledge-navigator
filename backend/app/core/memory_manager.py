import numpy as np

# Compatibilità NumPy 2.x: alcune librerie (es. ChromaDB<=0.4.x) usano alias rimossi
if not hasattr(np, "float_"):
    np.float_ = np.float64  # type: ignore[attr-defined]
if not hasattr(np, "int_"):
    np.int_ = np.int64  # type: ignore[attr-defined]
if not hasattr(np, "uint"):
    np.uint = np.uint64  # type: ignore[attr-defined]

import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from uuid import UUID
import json

from app.core.config import settings
from app.models.database import MemoryShort, MemoryMedium, MemoryLong
from app.services.embedding_service import EmbeddingService


class MemoryManager:
    """
    Manages multi-level memory system:
    - Short-term: In-memory context (session-specific)
    - Medium-term: Session-specific persisted memory
    - Long-term: Shared cross-session knowledge base
    """
    
    def __init__(self):
        # ChromaDB client
        self.chroma_client = chromadb.HttpClient(
            host=settings.chromadb_host,
            port=settings.chromadb_port,
        )
        
        # Collections
        self.file_embeddings_collection = self.chroma_client.get_or_create_collection(
            name="file_embeddings",
            metadata={"hnsw:space": "cosine"},
        )
        self.session_memory_collection = self.chroma_client.get_or_create_collection(
            name="session_memory",
            metadata={"hnsw:space": "cosine"},
        )
        self.long_term_memory_collection = self.chroma_client.get_or_create_collection(
            name="long_term_memory",
            metadata={"hnsw:space": "cosine"},
        )
        
        self.embedding_service = EmbeddingService()
        
        # In-memory short-term storage
        self.short_term_memory: Dict[UUID, Dict[str, Any]] = {}

    # Short-term Memory
    async def get_short_term_memory(
        self,
        db: AsyncSession,
        session_id: UUID,
    ) -> Optional[Dict[str, Any]]:
        """Get short-term memory for a session"""
        now = datetime.now(timezone.utc)
        
        # Check in-memory first
        if session_id in self.short_term_memory:
            memory = self.short_term_memory[session_id]
            expires_at = memory.get("expires_at")
            # Make sure both datetimes are timezone-aware for comparison
            if isinstance(expires_at, datetime):
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if expires_at > now:
                    return memory.get("context_data")
            del self.short_term_memory[session_id]
        
        # Check database
        result = await db.execute(
            select(MemoryShort).where(MemoryShort.session_id == session_id)
        )
        memory_short = result.scalar_one_or_none()
        
        if memory_short:
            expires_at = memory_short.expires_at
            # Make sure both datetimes are timezone-aware for comparison
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            
            if expires_at > now:
                context_data = memory_short.context_data
                # Cache in memory
                self.short_term_memory[session_id] = {
                    "context_data": context_data,
                    "expires_at": expires_at,
                }
                return context_data
        
        return None

    async def update_short_term_memory(
        self,
        db: AsyncSession,
        session_id: UUID,
        context_data: Dict[str, Any],
    ):
        """Update short-term memory"""
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.short_term_memory_ttl)
        
        # Update in-memory cache
        self.short_term_memory[session_id] = {
            "context_data": context_data,
            "expires_at": expires_at,
        }
        
        # Update database
        result = await db.execute(
            select(MemoryShort).where(MemoryShort.session_id == session_id)
        )
        memory_short = result.scalar_one_or_none()
        
        if memory_short:
            memory_short.context_data = context_data
            memory_short.expires_at = expires_at
        else:
            memory_short = MemoryShort(
                session_id=session_id,
                context_data=context_data,
                expires_at=expires_at,
            )
            db.add(memory_short)
        
        await db.commit()

    # Medium-term Memory
    async def add_medium_term_memory(
        self,
        db: AsyncSession,
        session_id: UUID,
        content: str,
    ):
        """Add content to medium-term memory"""
        # Generate embedding
        embedding = self.embedding_service.generate_embedding(content)
        
        # Store in ChromaDB
        embedding_id = f"medium_{session_id}_{datetime.now().isoformat()}"
        self.session_memory_collection.add(
            ids=[embedding_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[{"session_id": str(session_id)}],
        )
        
        # Store in PostgreSQL
        memory_medium = MemoryMedium(
            session_id=session_id,
            content=content,
            embedding_id=embedding_id,
        )
        db.add(memory_medium)
        await db.commit()

    async def retrieve_medium_term_memory(
        self,
        session_id: UUID,
        query: str,
        n_results: int = 5,
    ) -> List[str]:
        """Retrieve relevant medium-term memory for a session"""
        query_embedding = self.embedding_service.generate_embedding(query)
        
        results = self.session_memory_collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where={"session_id": str(session_id)},
        )
        
        return results.get("documents", [[]])[0] if results else []

    # Long-term Memory
    async def add_long_term_memory(
        self,
        db: AsyncSession,
        content: str,
        learned_from_sessions: List[UUID],
        importance_score: float = 0.5,
    ):
        """Add content to long-term memory"""
        # Generate embedding
        embedding = self.embedding_service.generate_embedding(content)
        
        # Store in ChromaDB
        embedding_id = f"long_{datetime.now().isoformat()}"
        # ChromaDB doesn't accept lists in metadata, so convert to comma-separated string
        learned_from_str = ",".join([str(sid) for sid in learned_from_sessions])
        self.long_term_memory_collection.add(
            ids=[embedding_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[
                {
                    "importance_score": importance_score,
                    "learned_from": learned_from_str,  # String instead of list
                }
            ],
        )
        
        # Store in PostgreSQL
        # Convert UUIDs to strings for JSONB storage
        learned_from_sessions_str = [str(sid) for sid in learned_from_sessions]
        memory_long = MemoryLong(
            content=content,
            embedding_id=embedding_id,
            learned_from_sessions=learned_from_sessions_str,  # Store as strings for JSONB
            importance_score=importance_score,
        )
        db.add(memory_long)
        await db.commit()

    async def retrieve_long_term_memory(
        self,
        query: str,
        n_results: int = 5,
        min_importance: float = None,
    ) -> List[str]:
        """Retrieve relevant long-term memory"""
        query_embedding = self.embedding_service.generate_embedding(query)
        
        where = {}
        if min_importance is not None:
            where["importance_score"] = {"$gte": min_importance}
        
        results = self.long_term_memory_collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where if where else None,
        )
        
        return results.get("documents", [[]])[0] if results else []

    async def should_store_in_long_term(
        self,
        content: str,
        importance_score: float,
    ) -> bool:
        """Determine if content should be stored in long-term memory"""
        return importance_score >= settings.long_term_importance_threshold

    # File Embeddings
    async def retrieve_file_content(
        self,
        session_id: UUID,
        query: str,
        n_results: int = 5,
        db: Optional[AsyncSession] = None,
    ) -> List[str]:
        """Retrieve relevant file content for a session based on query"""
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # First, check if there are any files for this session
            session_id_str = str(session_id)
            all_files = self.file_embeddings_collection.get(
                where={"session_id": session_id_str},
            )
            
            logger.info(f"Checking files for session {session_id_str}: found {len(all_files.get('ids', []))} embeddings in ChromaDB")
            
            if not all_files.get("ids"):
                logger.warning(f"No files found in ChromaDB for session {session_id_str}")
                return []
            
            # If db is provided, filter out embeddings for files that no longer exist
            valid_file_ids = None
            file_upload_times = {}  # Initialize here so it's available in outer scope
            if db is not None:
                logger.info(f"Database provided, will filter deleted files for session {session_id_str}")
                try:
                    from sqlalchemy import select
                    from app.models.database import File as FileModel
                    
                    # Get all existing file IDs for this session from database
                    from sqlalchemy.ext.asyncio import AsyncSession
                    
                    # Get file IDs with upload times for ordering
                    file_result = await db.execute(
                        select(FileModel.id, FileModel.uploaded_at)
                        .where(FileModel.session_id == session_id)
                        .order_by(FileModel.uploaded_at.desc())  # Most recent first
                    )
                    file_records = file_result.all()
                    existing_file_ids = {str(fid) for fid, _ in file_records}
                    valid_file_ids = existing_file_ids
                    
                    # Create a map of file_id -> upload_time for prioritization
                    file_upload_times = {str(fid): uploaded_at for fid, uploaded_at in file_records}
                    
                    logger.info(f"Found {len(existing_file_ids)} valid file IDs in database for session {session_id_str}: {existing_file_ids}")
                    
                    # Filter embeddings to only include existing files
                    metadata_list = all_files.get("metadatas", [])
                    ids_list = all_files.get("ids", [])
                    documents_list = all_files.get("documents", [])
                    
                    valid_indices = []
                    for i, metadata in enumerate(metadata_list):
                        file_id = None
                        if isinstance(metadata, dict):
                            file_id = metadata.get("file_id")
                        elif metadata is not None:
                            # Try to extract file_id from non-dict metadata
                            try:
                                if hasattr(metadata, 'get'):
                                    file_id = metadata.get("file_id")
                                elif hasattr(metadata, '__dict__'):
                                    file_id = getattr(metadata, 'file_id', None)
                            except:
                                pass
                        
                        if file_id and str(file_id) in existing_file_ids:
                            valid_indices.append(i)
                        elif file_id:
                            logger.debug(f"Filtering out embedding for deleted file_id: {file_id}")
                    
                    if len(valid_indices) < len(ids_list):
                        logger.info(f"Filtered out {len(ids_list) - len(valid_indices)} embeddings for deleted files")
                        # Update all_files to only include valid files
                        if valid_indices:
                            all_files = {
                                "ids": [ids_list[i] for i in valid_indices],
                                "documents": [documents_list[i] for i in valid_indices],
                                "metadatas": [metadata_list[i] for i in valid_indices],
                            }
                        else:
                            logger.warning("No valid files found after filtering deleted files")
                            return []
                except Exception as e:
                    logger.warning(f"Could not filter deleted files: {e}, proceeding with all embeddings")
            
            if not all_files.get("ids"):
                logger.warning(f"No valid files found in ChromaDB for session {session_id_str}")
                return []
            
            # Strategy: Get ALL files for the session, sort by upload time (most recent first)
            # This ensures the most recent file is ALWAYS returned first, regardless of semantic relevance
            if valid_file_ids and file_upload_times:
                # Get ALL files for this session from ChromaDB (not using semantic search)
                # This ensures we have the most recent file even if it's not semantically relevant
                all_session_files = self.file_embeddings_collection.get(
                    where={"session_id": session_id_str}
                )
                
                # Filter to only valid files and sort by upload time
                all_ids = all_session_files.get("ids", [])
                all_docs = all_session_files.get("documents", [])
                all_metas = all_session_files.get("metadatas", [])
                
                # Create list of (doc, file_id, upload_time) tuples
                file_items = []
                for i, doc in enumerate(all_docs):
                    if i < len(all_metas):
                        meta = all_metas[i]
                        file_id = None
                        if isinstance(meta, dict):
                            file_id = meta.get("file_id")
                        elif meta is not None:
                            try:
                                if hasattr(meta, 'get'):
                                    file_id = meta.get("file_id")
                                elif hasattr(meta, '__dict__'):
                                    file_id = getattr(meta, 'file_id', None)
                            except:
                                pass
                        
                        # Only include valid files
                        if file_id and str(file_id) in valid_file_ids:
                            upload_time = file_upload_times.get(str(file_id), datetime.min.replace(tzinfo=timezone.utc))
                            file_items.append((doc, str(file_id), upload_time))
                
                # Sort by upload time ONLY - most recent first
                file_items.sort(key=lambda x: x[2], reverse=True)
                
                logger.info(f"Retrieved {len(file_items)} files, sorted by upload time. First file: {file_items[0][1] if file_items else 'none'}")
                
                # Return only the documents (without file_id and upload_time)
                # Limit document size to avoid overwhelming the model and causing timeouts
                filtered_docs = []
                for doc, file_id, _ in file_items[:n_results]:
                    # Truncate very long documents (keep first 15000 chars to allow for summaries)
                    if len(doc) > 15000:
                        truncated_doc = doc[:15000] + f"\n\n[Content truncated - original was {len(doc)} characters. This is a large file, focusing on the beginning.]"
                        filtered_docs.append(truncated_doc)
                        logger.info(f"Truncated document for file {file_id} from {len(doc)} to {len(truncated_doc)} chars")
                    else:
                        filtered_docs.append(doc)
                
                logger.info(f"Returning {len(filtered_docs)} documents, ordered by upload time (most recent first)")
                
                return filtered_docs
            
            # Fallback: if we don't have file_upload_times, use semantic search
            # Generate query embedding
            query_embedding = self.embedding_service.generate_embedding(query)
            
            # Query with semantic search (with filtered file_ids if available)
            where_clause = {"session_id": session_id_str}
            if valid_file_ids:
                # Note: ChromaDB where clause doesn't support IN directly, so we'll filter after
                where_clause = {"session_id": session_id_str}
            
            # Query ALL files for this session to ensure we don't miss the most recent one
            # We'll filter and sort by upload time after
            query_n_results = len(all_files.get("ids", []))  # Get ALL files to ensure we have the most recent
            
            results = self.file_embeddings_collection.query(
                query_embeddings=[query_embedding],
                n_results=query_n_results if query_n_results > 0 else 1,
                where=where_clause,
            )
            
            documents = results.get("documents", [[]])
            metadatas_result = results.get("metadatas", [[]])
            
            if documents and len(documents) > 0:
                file_documents = documents[0]
                metadata_list = metadatas_result[0] if metadatas_result else []
                
                # Final filter: ensure we only return documents for existing files
                # Also prioritize by file upload time (more recent files first)
                if valid_file_ids and metadata_list:
                    filtered_items = []  # List of (doc, file_id) tuples
                    for doc, meta in zip(file_documents, metadata_list):
                        file_id = None
                        if isinstance(meta, dict):
                            file_id = meta.get("file_id")
                        elif meta is not None:
                            # Try to extract file_id from non-dict metadata
                            try:
                                if hasattr(meta, 'get'):
                                    file_id = meta.get("file_id")
                                elif hasattr(meta, '__dict__'):
                                    file_id = getattr(meta, 'file_id', None)
                            except:
                                pass
                        
                        if file_id and str(file_id) in valid_file_ids:
                            filtered_items.append((doc, file_id))
                        elif file_id:
                            logger.debug(f"Filtering out document for deleted file_id: {file_id}")
                    
                    if filtered_items:
                        # ALWAYS sort by upload time (more recent files first)
                        # Priority order: Most recent file gets highest priority regardless of semantic relevance
                        if valid_file_ids and file_upload_times:
                            try:
                                # Sort ONLY by upload time - most recent first, ignoring semantic relevance
                                # This ensures the newest file is always returned first
                                filtered_items.sort(
                                    key=lambda x: file_upload_times.get(x[1], datetime.min.replace(tzinfo=timezone.utc)),
                                    reverse=True  # Most recent first
                                )
                                
                                # Log which file is being returned first
                                if filtered_items:
                                    first_file_id = filtered_items[0][1]
                                    first_upload_time = file_upload_times.get(first_file_id, None)
                                    logger.info(f"Sorted {len(filtered_items)} items by upload time. First file: {first_file_id}, uploaded: {first_upload_time}")
                                    
                                    if prioritized_file_ids and len(prioritized_file_ids) > 0:
                                        expected_first = prioritized_file_ids[0]
                                        if first_file_id == expected_first:
                                            logger.info(f"✅ Correct priority: Most recent file ({first_file_id}) is first")
                                        else:
                                            logger.warning(f"⚠️ Priority mismatch: Expected {expected_first}, got {first_file_id}")
                            except Exception as e:
                                logger.error(f"Could not sort by upload time: {e}", exc_info=True)
                        else:
                            logger.warning("Cannot sort by upload time: missing file_upload_times or valid_file_ids")
                        
                        # Extract documents in the sorted order (most recent first)
                        filtered_docs = [doc for doc, _ in filtered_items]
                        
                        # Log which file IDs are being returned to verify order
                        if filtered_items and len(filtered_items) > 0:
                            first_file_ids = [fid for _, fid in filtered_items[:min(3, len(filtered_items))]]
                            logger.info(f"Returning {len(filtered_docs)} documents from files (in order by upload time): {first_file_ids}")
                            
                            # Verify the first file is actually the most recent
                            if len(first_file_ids) > 0 and file_upload_times:
                                first_file_id = first_file_ids[0]
                                first_time = file_upload_times.get(first_file_id)
                                
                                # Check all other files to ensure none is more recent
                                all_times = [(fid, file_upload_times.get(fid)) for fid in first_file_ids if fid in file_upload_times]
                                if all_times:
                                    most_recent = max(all_times, key=lambda x: x[1] if x[1] else datetime.min.replace(tzinfo=timezone.utc))
                                    if most_recent[0] != first_file_id:
                                        logger.error(f"❌ ORDERING BUG: First file {first_file_id} is NOT the most recent! Most recent is {most_recent[0]}")
                                    else:
                                        logger.info(f"✅ Verified: First file {first_file_id} is the most recent")
                        
                        return filtered_docs[:n_results]
                    else:
                        logger.warning("All retrieved documents were for deleted files")
                        return []
                else:
                    logger.info(f"Retrieved {len(file_documents)} file documents for query: {query[:50]}...")
                    return file_documents[:n_results]
            
            # Fallback: if semantic search fails, return all files for this session (but only valid ones)
            logger.warning(f"Semantic search returned no results, falling back to all files")
            if all_files.get("documents"):
                # Ensure we only return valid files even in fallback
                if valid_file_ids:
                    fallback_docs = []
                    for i, doc in enumerate(all_files.get("documents", [])):
                        meta = all_files.get("metadatas", [])[i] if i < len(all_files.get("metadatas", [])) else {}
                        
                        file_id = None
                        if isinstance(meta, dict):
                            file_id = meta.get("file_id")
                        elif meta is not None:
                            try:
                                if hasattr(meta, 'get'):
                                    file_id = meta.get("file_id")
                                elif hasattr(meta, '__dict__'):
                                    file_id = getattr(meta, 'file_id', None)
                            except:
                                pass
                        
                        if file_id and str(file_id) in valid_file_ids:
                            fallback_docs.append(doc)
                        elif file_id:
                            logger.debug(f"Filtering out fallback document for deleted file_id: {file_id}")
                    
                    if fallback_docs:
                        logger.info(f"Returning {len(fallback_docs)} valid files from fallback (filtered from {len(all_files.get('documents', []))})")
                        return fallback_docs[:n_results]
                    else:
                        logger.warning("All fallback documents were for deleted files")
                        return []
                else:
                    # No db provided, return all (but log warning)
                    logger.warning("No db provided to filter deleted files, returning all documents")
                    return all_files["documents"][:n_results]
            
            return []
        except Exception as e:
            logger.error(f"Error retrieving file content for session {session_id}: {e}", exc_info=True)
            return []

