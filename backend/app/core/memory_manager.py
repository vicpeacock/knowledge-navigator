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
import logging

from app.core.config import settings
from app.models.database import MemoryShort, MemoryMedium, MemoryLong
from app.services.embedding_service import EmbeddingService


class MemoryManager:
    """
    Manages multi-level memory system:
    - Short-term: In-memory context (session-specific)
    - Medium-term: Session-specific persisted memory
    - Long-term: Shared cross-session knowledge base
    
    Supports multi-tenant isolation via tenant-specific ChromaDB collections.
    """
    
    def __init__(self, tenant_id: Optional[UUID] = None):
        # ChromaDB client (shared across tenants)
        # Use CloudClient for cloud deployment, HttpClient for local
        if settings.chromadb_use_cloud and settings.chromadb_cloud_api_key:
            # ChromaDB Cloud (for cloud deployment)
            import logging
            logger = logging.getLogger(__name__)
            logger.info("Using ChromaDB Cloud client for cloud deployment")
            self.chroma_client = chromadb.CloudClient(
                api_key=settings.chromadb_cloud_api_key,
                tenant=settings.chromadb_cloud_tenant,
                database=settings.chromadb_cloud_database,
            )
        else:
            # ChromaDB HttpClient (for local development)
            self.chroma_client = chromadb.HttpClient(
                host=settings.chromadb_host,
                port=settings.chromadb_port,
            )
        
        # Store tenant_id for collection naming
        self.tenant_id = tenant_id
        
        # Collections cache (tenant-specific)
        self._collections_cache: Dict[str, Any] = {}
        
        self.embedding_service = EmbeddingService()
        
        # In-memory short-term storage
        self.short_term_memory: Dict[UUID, Dict[str, Any]] = {}
    def _get_collection_name(self, base_name: str, tenant_id: Optional[UUID] = None) -> str:
        """Generate tenant-specific collection name"""
        effective_tenant_id = tenant_id or self.tenant_id
        if effective_tenant_id:
            return f"{base_name}_{str(effective_tenant_id).replace('-', '_')}"
        else:
            return f"{base_name}_00000000_0000_0000_0000_000000000000"

    
    def _get_collection(self, base_name: str, tenant_id: Optional[UUID] = None):
        """Get or create tenant-specific collection"""
        collection_name = self._get_collection_name(base_name, tenant_id)
        
        # Check cache first
        if collection_name in self._collections_cache:
            return self._collections_cache[collection_name]
        
        metadata = {
            "tenant_id": str(tenant_id or self.tenant_id) if (tenant_id or self.tenant_id) else "00000000-0000-0000-0000-000000000000",
            "_type": "collection"
        }
        logger = logging.getLogger(__name__)
        collection = None
        
        # Strategy 1: Try to get existing collection first (without metadata requirements)
        try:
            collection = self.chroma_client.get_collection(name=collection_name)
            if collection:
                logger.info(
                    "✅ Successfully retrieved existing collection '%s'",
                    collection_name,
                )
                self._collections_cache[collection_name] = collection
                return collection
        except Exception as e:
            # Collection doesn't exist or has issues, continue to creation strategies
            error_str = str(e)
            if "'_type'" in error_str or "KeyError" in error_str:
                # Collection exists but has corrupted metadata - try to delete it
                logger.warning(f"⚠️  Collection '%s' exists but has corrupted metadata, attempting to delete...", collection_name)
                try:
                    self.chroma_client.delete_collection(name=collection_name)
                    logger.info(f"✅ Successfully deleted corrupted collection '%s'", collection_name)
                except Exception as delete_error:
                    logger.warning(f"⚠️  Could not delete collection '%s': {delete_error}", collection_name)
            pass
        
        # Strategy 2: Try to create with minimal metadata (no _type)
        # ChromaDB 0.6.0 might have issues with _type in metadata
        strategies = [
            lambda: self.chroma_client.create_collection(name=collection_name, metadata={"tenant_id": str(tenant_id or self.tenant_id) if (tenant_id or self.tenant_id) else "00000000-0000-0000-0000-000000000000"}),
            lambda: self.chroma_client.create_collection(name=collection_name, metadata={}),
            lambda: self.chroma_client.create_collection(name=collection_name),
            # Last resort: try with _type (might work if collection was deleted)
            lambda: self.chroma_client.create_collection(name=collection_name, metadata=metadata),
            lambda: self.chroma_client.get_or_create_collection(name=collection_name, metadata=metadata),
        ]
        strategy_names = [
            "create with tenant_id only",
            "create with empty metadata",
            "create without metadata",
            "create with full metadata (including _type)",
            "get_or_create with full metadata",
        ]
        
        last_error = None
        for strategy, strategy_name in zip(strategies, strategy_names):
            try:
                collection = strategy()
                if collection:
                    logger.info(
                        "✅ Successfully created collection '%s' using: %s",
                        collection_name,
                        strategy_name,
                    )
                    break
            except Exception as e:
                error_str = str(e)
                # Check if it's a KeyError related to _type
                if "'_type'" in error_str or "KeyError" in error_str:
                    logger.warning("⚠️  ChromaDB KeyError('_type') detected, trying next strategy...")
                    # If this is a KeyError and we haven't tried deleting yet, try to delete and retry
                    if "KeyError" in error_str and strategy_name == "create with tenant_id only":
                        try:
                            logger.warning(f"⚠️  Attempting to delete potentially corrupted collection '%s'...", collection_name)
                            self.chroma_client.delete_collection(name=collection_name)
                            logger.info(f"✅ Deleted collection '%s', retrying creation...", collection_name)
                            # Retry the same strategy after deletion
                            try:
                                collection = strategy()
                                if collection:
                                    logger.info(
                                        "✅ Successfully created collection '%s' after deletion using: %s",
                                        collection_name,
                                        strategy_name,
                                    )
                                    break
                            except Exception as retry_error:
                                logger.warning(f"⚠️  Retry after deletion failed: {retry_error}, continuing to next strategy...")
                        except Exception as delete_error:
                            logger.warning(f"⚠️  Could not delete collection '%s': {delete_error}, continuing...", collection_name)
                elif "already exists" in error_str.lower() or "duplicate" in error_str.lower():
                    # Collection exists but we couldn't get it - try to get it again
                    try:
                        collection = self.chroma_client.get_collection(name=collection_name)
                        if collection:
                            logger.info(
                                "✅ Successfully retrieved collection '%s' after 'already exists' error",
                                collection_name,
                            )
                            break
                    except Exception as get_error:
                        logger.warning(f"⚠️  Collection exists but cannot be retrieved: {get_error}, trying next strategy...")
                last_error = e
                continue
        
        if collection is None:
            error_msg = f"Failed to create collection '{collection_name}' after all retries"
            if last_error:
                error_msg += f": {last_error}"
            logger.error(f"❌ {error_msg}")
            return None
        
        self._collections_cache[collection_name] = collection
        return collection


    @property
    def file_embeddings_collection(self):
        """Get file embeddings collection for current tenant"""
        return self._get_collection("file_embeddings", self.tenant_id)
    
    @property
    def session_memory_collection(self):
        """Get session memory collection for current tenant"""
        return self._get_collection("session_memory", self.tenant_id)
    
    @property
    def long_term_memory_collection(self):
        """Get long-term memory collection for current tenant"""
        return self._get_collection("long_term_memory", self.tenant_id)

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
        tenant_id: Optional[UUID] = None,
    ):
        """Update short-term memory"""
        # Get tenant_id from parameter, self, or session
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            # Fallback: get tenant_id from session
            from app.models.database import Session as SessionModel
            session_result = await db.execute(
                select(SessionModel.tenant_id).where(SessionModel.id == session_id)
            )
            effective_tenant_id = session_result.scalar_one_or_none()
        
        if not effective_tenant_id:
            raise ValueError(f"Cannot update short-term memory: tenant_id is required for session {session_id}")
        
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.short_term_memory_ttl)
        
        # Update in-memory cache
        self.short_term_memory[session_id] = {
            "context_data": context_data,
            "expires_at": expires_at,
        }
        
        # Update database
        result = await db.execute(
            select(MemoryShort).where(
                MemoryShort.session_id == session_id,
                MemoryShort.tenant_id == effective_tenant_id
            )
        )
        memory_short = result.scalar_one_or_none()
        
        if memory_short:
            memory_short.context_data = context_data
            memory_short.expires_at = expires_at
            # Ensure tenant_id is set if it was missing
            if not memory_short.tenant_id:
                memory_short.tenant_id = effective_tenant_id
        else:
            memory_short = MemoryShort(
                tenant_id=effective_tenant_id,
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
        tenant_id: Optional[UUID] = None,
    ):
        """Add content to medium-term memory (for specific tenant)"""
        # Get tenant-specific collection
        effective_tenant_id = tenant_id or self.tenant_id
        
        # If tenant_id is still None, get it from session
        if not effective_tenant_id:
            from app.models.database import Session as SessionModel
            session_result = await db.execute(
                select(SessionModel.tenant_id).where(SessionModel.id == session_id)
            )
            effective_tenant_id = session_result.scalar_one_or_none()
        
        if not effective_tenant_id:
            raise ValueError(f"Cannot add medium-term memory: tenant_id is required for session {session_id}")
        
        collection = self._get_collection("session_memory", effective_tenant_id)
        
        # Generate embedding
        embedding = self.embedding_service.generate_embedding(content)
        
        # Store in ChromaDB
        embedding_id = f"medium_{session_id}_{datetime.now().isoformat()}"
        collection.add(
            ids=[embedding_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[{"session_id": str(session_id)}],
        )
        
        # Store in PostgreSQL
        memory_medium = MemoryMedium(
            tenant_id=effective_tenant_id,  # CRITICAL: tenant_id is required
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
        tenant_id: Optional[UUID] = None,
    ) -> List[str]:
        """Retrieve relevant medium-term memory for a session (for specific tenant)"""
        import asyncio
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Run embedding generation in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            query_embedding = await loop.run_in_executor(
                None, 
                self.embedding_service.generate_embedding, 
                query
            )
            
            # Get tenant-specific collection
            collection = self._get_collection("session_memory", tenant_id or self.tenant_id)
            
            # Handle case where collection creation failed (e.g., ChromaDB KeyError)
            if collection is None:
                logger.warning(f"⚠️  Could not get/create session_memory collection for tenant {tenant_id or self.tenant_id}, returning empty results")
                return []
            
            # Run ChromaDB query in thread pool (ChromaDB is synchronous)
            results = await loop.run_in_executor(
                None,
                lambda: collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    where={"session_id": str(session_id)},
                )
            )
            
            return results.get("documents", [[]])[0] if results else []
        except Exception as e:
            logger.error(f"Error in retrieve_medium_term_memory: {e}", exc_info=True)
            return []

    # Long-term Memory
    async def add_long_term_memory(
        self,
        db: AsyncSession,
        content: str,
        learned_from_sessions: List[UUID],
        importance_score: float = 0.5,
        tenant_id: Optional[UUID] = None,
        check_duplicates: bool = True,
        similarity_threshold: float = 0.85,
    ):
        """
        Add content to long-term memory (for specific tenant).
        
        Args:
            db: Database session
            content: Content to store
            learned_from_sessions: List of session IDs where this was learned
            importance_score: Importance score (0.0-1.0)
            tenant_id: Tenant ID (optional)
            check_duplicates: If True, check for similar memories before adding (default: True)
            similarity_threshold: Similarity threshold for duplicate detection (default: 0.85)
        
        Returns:
            Tuple[bool, Optional[str]]: (was_added, existing_memory_id_or_none)
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Check for duplicates if enabled
        if check_duplicates:
            try:
                # Retrieve similar memories
                similar = await self.retrieve_long_term_memory(
                    query=content,
                    n_results=3,
                    min_importance=0.0,  # Check all importance levels
                    tenant_id=tenant_id,
                )
                
                if similar:
                    # Calculate similarity using embeddings
                    content_embedding = self.embedding_service.generate_embedding(content)
                    
                    for similar_content in similar:
                        similar_embedding = self.embedding_service.generate_embedding(similar_content)
                        
                        # Calculate cosine similarity
                        similarity = np.dot(content_embedding, similar_embedding) / (
                            np.linalg.norm(content_embedding) * np.linalg.norm(similar_embedding)
                        )
                        
                        if similarity >= similarity_threshold:
                            logger.info(f"⚠️  Duplicate memory detected (similarity: {similarity:.2f}), skipping: {content[:50]}...")
                            # Find the existing memory ID from database
                            # Note: similar_content might have formatting (e.g., [PERSONAL_INFO] prefix),
                            # so we search by content similarity or exact match
                            from sqlalchemy import select
                            # MemoryLong is already imported at the top of the file
                            
                            # Try exact match first
                            result = await db.execute(
                                select(MemoryLong).where(
                                    MemoryLong.content == similar_content,
                                    MemoryLong.tenant_id == (tenant_id or self.tenant_id)
                                ).limit(1)
                            )
                            existing_memory = result.scalar_one_or_none()
                            
                            # If not found, try to find by content without prefix (in case formatting differs)
                            if not existing_memory:
                                # Extract content without prefix (e.g., remove [PERSONAL_INFO] prefix)
                                content_without_prefix = similar_content
                                for prefix in ["[PERSONAL_INFO]", "[FACT]", "[PREFERENCE]", "[CONTACT]", "[PROJECT]"]:
                                    if similar_content.startswith(prefix):
                                        content_without_prefix = similar_content[len(prefix):].strip()
                                        break
                                
                                # Also try without prefix from new content
                                new_content_without_prefix = content
                                for prefix in ["[PERSONAL_INFO]", "[FACT]", "[PREFERENCE]", "[CONTACT]", "[PROJECT]"]:
                                    if content.startswith(prefix):
                                        new_content_without_prefix = content[len(prefix):].strip()
                                        break
                                
                                # Search for memories that match either stripped version
                                result = await db.execute(
                                    select(MemoryLong).where(
                                        MemoryLong.tenant_id == (tenant_id or self.tenant_id)
                                    )
                                )
                                all_memories = result.scalars().all()
                                
                                for mem in all_memories:
                                    mem_content = mem.content
                                    # Remove prefix if present
                                    for prefix in ["[PERSONAL_INFO]", "[FACT]", "[PREFERENCE]", "[CONTACT]", "[PROJECT]"]:
                                        if mem_content.startswith(prefix):
                                            mem_content = mem_content[len(prefix):].strip()
                                            break
                                    
                                    # Check if stripped contents match
                                    if mem_content == content_without_prefix or mem_content == new_content_without_prefix:
                                        existing_memory = mem
                                        break
                            
                            if existing_memory:
                                # Update learned_from_sessions to include new sessions
                                existing_sessions = set(existing_memory.learned_from_sessions or [])
                                new_sessions = set([str(sid) for sid in learned_from_sessions])
                                existing_memory.learned_from_sessions = list(existing_sessions | new_sessions)
                                # Update importance if new one is higher
                                if importance_score > existing_memory.importance_score:
                                    existing_memory.importance_score = importance_score
                                await db.commit()
                                logger.info(f"✅ Updated existing memory with new session IDs: {existing_memory.id}")
                            return (False, str(existing_memory.id) if existing_memory else None)
            except Exception as e:
                logger.warning(f"Error checking for duplicate memories: {e}, proceeding with add")
        
        # Generate embedding
        embedding = self.embedding_service.generate_embedding(content)
        
        # Get tenant-specific collection
        effective_tenant_id = tenant_id or self.tenant_id
        collection = self._get_collection("long_term_memory", effective_tenant_id)

        # Handle case where collection creation failed (e.g., ChromaDB KeyError)
        if collection is None:
            logger.warning(
                "⚠️  Could not get/create long_term_memory collection for tenant %s, "
                "skipping add_long_term_memory",
                effective_tenant_id,
            )
            return (False, None)

        # Store in ChromaDB
        embedding_id = f"long_{datetime.now().isoformat()}"
        # ChromaDB doesn't accept lists in metadata, so convert to comma-separated string
        learned_from_str = ",".join([str(sid) for sid in learned_from_sessions])
        collection.add(
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
            tenant_id=tenant_id,
        )
        db.add(memory_long)
        await db.commit()
        logger.info(f"✅ Added new long-term memory: {content[:50]}...")
        return (True, str(memory_long.id))

    async def retrieve_long_term_memory(
        self,
        query: str,
        n_results: int = 5,
        min_importance: float = None,
        tenant_id: Optional[UUID] = None,
    ) -> List[str]:
        """Retrieve relevant long-term memory (for specific tenant)"""
        import asyncio
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Run embedding generation in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            query_embedding = await loop.run_in_executor(
                None,
                self.embedding_service.generate_embedding,
                query
            )
            
            # Get tenant-specific collection
            effective_tenant_id = tenant_id or self.tenant_id
            collection = self._get_collection("long_term_memory", effective_tenant_id)
            
            # Handle case where collection creation failed (e.g., ChromaDB KeyError)
            if collection is None:
                logger.warning(f"⚠️  Could not get/create long_term_memory collection for tenant {effective_tenant_id}, returning empty results")
                return []
            
            where = {}
            if min_importance is not None:
                where["importance_score"] = {"$gte": min_importance}
            
            # Run ChromaDB query in thread pool (ChromaDB is synchronous)
            results = await loop.run_in_executor(
                None,
                lambda: collection.query(
                    query_embeddings=[query_embedding],
                    n_results=n_results,
                    where=where if where else None,
                )
            )
            
            return results.get("documents", [[]])[0] if results else []
        except Exception as e:
            error_str = str(e).lower()
            # ChromaDB HNSW index errors are often recoverable - log as warning
            if "contigious" in error_str or "ef or m is too small" in error_str or "hnsw" in error_str:
                logger.warning(f"⚠️  ChromaDB index configuration issue (may need index rebuild): {e}")
                logger.debug(f"   This is usually caused by ChromaDB HNSW index parameters. Consider rebuilding the collection.")
            else:
                logger.error(f"Error in retrieve_long_term_memory: {e}", exc_info=True)
            return []

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
        user_id: UUID,  # Changed: files are now user-scoped, not session-scoped
        query: str,
        n_results: int = 5,
        db: Optional[AsyncSession] = None,
        tenant_id: Optional[UUID] = None,
        session_id: Optional[UUID] = None,  # Optional: for backward compatibility and context
    ) -> List[str]:
        """Retrieve relevant file content for a user based on query"""
        import logging
        import re
        logger = logging.getLogger(__name__)
        
        # Check if query contains a file ID (UUID format)
        # Pattern: UUID format (8-4-4-4-12 hex digits)
        uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
        file_id_match = re.search(uuid_pattern, query, re.IGNORECASE)
        requested_file_id = None
        if file_id_match:
            requested_file_id = file_id_match.group(0)
            logger.info(f"Detected file ID in query: {requested_file_id}")
        
        # Check if query is a generic file request (summary, analyze, etc.)
        # These queries should retrieve ALL files, not use semantic search
        query_lower = query.lower()
        generic_file_keywords = [
            "riassunto", "riassumere", "summary", "summarize", "analizza", "analyze", 
            "ultimo file", "last file", "most recent file", "latest file",
            "il file", "the file", "questo file", "this file",
            "contenuto del file", "file content", "contenuto file", "contenuto caricato",
            "spiegami", "explain", "descrivi", "describe", "cosa consiste", "what is",
            "nel documento", "in the document", "nel file", "in the file",
            "documento", "document", "pdf", ".pdf",
            "caricato in memoria", "uploaded file", "file caricato", "file in memoria"
        ]
        is_generic_file_request = any(keyword in query_lower for keyword in generic_file_keywords)
        
        if is_generic_file_request:
            logger.info(f"Detected generic file request: '{query}'. Will retrieve all files for user instead of semantic search.")
        
        try:
            # Get tenant-specific collection
            effective_tenant_id = tenant_id or self.tenant_id
            collection = self._get_collection("file_embeddings", effective_tenant_id)
            
            # If a specific file ID was requested, try to retrieve it directly
            if requested_file_id and db is not None:
                logger.info(f"Attempting to retrieve file by ID: {requested_file_id}")
                try:
                    # First verify the file exists in the database and belongs to this session
                    from sqlalchemy import select
                    from app.models.database import File as FileModel
                    
                    file_result = await db.execute(
                        select(FileModel).where(
                            FileModel.id == UUID(requested_file_id),
                            FileModel.user_id == user_id,  # Files are user-scoped now
                            FileModel.tenant_id == effective_tenant_id
                        )
                    )
                    file_record = file_result.scalar_one_or_none()
                    
                    if file_record:
                        logger.info(f"File {requested_file_id} found in database, retrieving from ChromaDB")
                        # Try to get the file content from ChromaDB by file_id in metadata
                        try:
                            # Try different where clause syntaxes for ChromaDB Cloud compatibility
                            file_embeddings = None
                            where_clauses = [
                                {"file_id": requested_file_id},  # Standard syntax
                                {"file_id": {"$eq": requested_file_id}},  # MongoDB-style syntax
                            ]
                            
                            for where_clause in where_clauses:
                                try:
                                    logger.debug(f"Trying where clause: {where_clause}")
                                    file_embeddings = collection.get(where=where_clause)
                                    if file_embeddings.get("documents"):
                                        break  # Found it, exit loop
                                except Exception as clause_error:
                                    logger.debug(f"Where clause {where_clause} failed: {clause_error}, trying next...")
                                    continue
                            
                            # If still not found, try getting all files and filtering manually
                            if not file_embeddings or not file_embeddings.get("documents"):
                                logger.info(f"Direct query failed, trying manual filter for file_id {requested_file_id}")
                                user_id_str = str(user_id)
                                all_user_files = collection.get(
                                    where={"user_id": user_id_str}
                                )
                                all_ids = all_user_files.get("ids", [])
                                all_docs = all_user_files.get("documents", [])
                                all_metas = all_user_files.get("metadatas", [])
                                
                                for i, meta in enumerate(all_metas):
                                    file_id = None
                                    if isinstance(meta, dict):
                                        file_id = meta.get("file_id")
                                    if file_id == requested_file_id:
                                        doc = all_docs[i]
                                        logger.info(f"✅ Retrieved file {requested_file_id} from ChromaDB (manual filter), content length: {len(doc)} chars")
                                        # Truncate if too long
                                        if len(doc) > 15000:
                                            doc = doc[:15000] + f"\n\n[Content truncated - original was {len(doc)} characters. This is a large file, focusing on the beginning.]"
                                        return [doc]
                            
                            if file_embeddings and file_embeddings.get("documents"):
                                # Found the file in ChromaDB
                                doc = file_embeddings["documents"][0]
                                logger.info(f"✅ Retrieved file {requested_file_id} from ChromaDB, content length: {len(doc)} chars")
                                # Truncate if too long
                                if len(doc) > 15000:
                                    doc = doc[:15000] + f"\n\n[Content truncated - original was {len(doc)} characters. This is a large file, focusing on the beginning.]"
                                return [doc]
                            else:
                                logger.warning(f"File {requested_file_id} exists in database but not found in ChromaDB embeddings. Collection has {len(collection.get().get('ids', []))} total embeddings.")
                        except Exception as chroma_error:
                            logger.error(f"Error retrieving file {requested_file_id} from ChromaDB: {chroma_error}", exc_info=True)
                    else:
                        logger.info(f"File {requested_file_id} not found in database for user {user_id}")
                except ValueError as uuid_error:
                    logger.warning(f"Invalid UUID format in query: {requested_file_id}, error: {uuid_error}")
                except Exception as e:
                    logger.warning(f"Error checking file ID {requested_file_id}: {e}")
                    # Continue with normal retrieval flow
            
            # Handle case where collection creation failed (e.g., ChromaDB KeyError)
            if collection is None:
                logger.warning(f"⚠️  Could not get/create file_embeddings collection for tenant {effective_tenant_id}, returning empty results")
                return []
            
            # First, check if there are any files for this user
            user_id_str = str(user_id)
            logger.info(f"🔍 Retrieving files for user {user_id_str}, tenant: {effective_tenant_id}, collection: {collection.name if hasattr(collection, 'name') else 'unknown'}")
            
            try:
                # Query by user_id (files are now user-scoped)
                all_files = collection.get(
                    where={"user_id": user_id_str},
                )
                logger.info(f"✅ ChromaDB query successful: found {len(all_files.get('ids', []))} embeddings for user {user_id_str}")
            except Exception as get_error:
                logger.error(f"❌ Error querying ChromaDB collection: {get_error}", exc_info=True)
                # Try without where clause to see if collection has any data
                try:
                    all_files_raw = collection.get()
                    logger.warning(f"⚠️  Query with where clause failed, but collection has {len(all_files_raw.get('ids', []))} total embeddings")
                    logger.warning(f"   Trying to filter manually...")
                    # Filter manually
                    all_ids = all_files_raw.get("ids", [])
                    all_docs = all_files_raw.get("documents", [])
                    all_metas = all_files_raw.get("metadatas", [])
                    filtered_ids = []
                    filtered_docs = []
                    filtered_metas = []
                    for i, meta in enumerate(all_metas):
                        meta_user_id = None
                        if isinstance(meta, dict):
                            meta_user_id = meta.get("user_id")
                        if meta_user_id == user_id_str:
                            filtered_ids.append(all_ids[i])
                            filtered_docs.append(all_docs[i])
                            filtered_metas.append(meta)
                    all_files = {
                        "ids": filtered_ids,
                        "documents": filtered_docs,
                        "metadatas": filtered_metas,
                    }
                    logger.info(f"✅ Manual filter successful: found {len(filtered_ids)} embeddings for user {user_id_str}")
                except Exception as fallback_error:
                    logger.error(f"❌ Fallback query also failed: {fallback_error}", exc_info=True)
                    return []
            
            if not all_files.get("ids"):
                logger.warning(f"⚠️  No files found in ChromaDB for user {user_id_str} (tenant: {effective_tenant_id})")
                # Check if there are any files in the database for this user
                if db is not None:
                    try:
                        from sqlalchemy import select
                        from app.models.database import File as FileModel
                        from pathlib import Path
                        from app.services.file_processor import FileProcessor
                        from app.core.config import settings
                        
                        # Get file records with filepath (user-scoped now)
                        db_file_result = await db.execute(
                            select(FileModel.id, FileModel.filename, FileModel.filepath, FileModel.mime_type).where(
                                FileModel.user_id == user_id,  # Files are user-scoped
                                FileModel.tenant_id == effective_tenant_id
                            ).order_by(FileModel.uploaded_at.desc())
                        )
                        db_files = db_file_result.all()
                        
                        if db_files:
                            logger.warning(f"⚠️  Found {len(db_files)} files in database but 0 embeddings in ChromaDB. Attempting to retrieve content directly from files.")
                            logger.warning(f"   Database file IDs: {[str(fid) for fid, _, _, _ in db_files[:5]]}{'...' if len(db_files) > 5 else ''}")
                            
                            # Try to retrieve content directly from file system
                            file_processor = FileProcessor()
                            retrieved_contents = []
                            
                            for file_id, filename, filepath, mime_type in db_files[:n_results]:
                                try:
                                    file_path = Path(filepath)
                                    if file_path.exists():
                                        logger.info(f"📄 File exists on filesystem: {filename}, attempting to extract content...")
                                        # Extract text from file
                                        file_data = file_processor.extract_text(str(file_path), mime_type)
                                        
                                        if file_data.get("text"):
                                            text_content = file_data["text"]
                                            # Truncate if too long
                                            if len(text_content) > 15000:
                                                text_content = text_content[:15000] + f"\n\n[Content truncated - original was {len(text_content)} characters. This is a large file, focusing on the beginning.]"
                                            retrieved_contents.append(text_content)
                                            logger.info(f"✅ Retrieved content from file {filename}, length: {len(text_content)} chars")
                                            
                                            # Try to create embedding now (async, don't wait)
                                            try:
                                                embedding = self.embedding_service.generate_embedding(text_content)
                                                embedding_id = f"file_{file_id}"
                                                
                                                # Truncate text for ChromaDB
                                                text_for_embedding = text_content
                                                if len(text_for_embedding) > 20000:
                                                    text_for_embedding = text_for_embedding[:20000] + "... [truncated]"
                                                
                                                collection.add(
                                                    ids=[embedding_id],
                                                    embeddings=[embedding],
                                                    documents=[text_for_embedding],
                                                    metadatas=[{
                                                        "user_id": user_id_str,  # Files are user-scoped, not session-scoped
                                                        "file_id": str(file_id),
                                                        "filename": filename,
                                                        "session_id": session_id_str if session_id else None,  # Optional: for backward compatibility
                                                    }],
                                                )
                                                logger.info(f"✅ Created embedding for file {filename} (ID: {file_id})")
                                            except Exception as embed_error:
                                                logger.warning(f"⚠️  Could not create embedding for file {filename}: {embed_error}")
                                        else:
                                            logger.warning(f"⚠️  No text extracted from file {filename}")
                                    else:
                                        logger.error(f"❌ File not found on filesystem: {filepath}")
                                        logger.error(f"   This is expected on Cloud Run (ephemeral filesystem).")
                                        logger.error(f"   File metadata exists in database but file content was lost when container restarted.")
                                        logger.error(f"   Solution: User needs to re-upload the file. File ID: {file_id}")
                                except Exception as file_error:
                                    logger.warning(f"⚠️  Error retrieving content from file {filename}: {file_error}")
                            
                            if retrieved_contents:
                                logger.info(f"✅ Retrieved {len(retrieved_contents)} file contents directly from filesystem")
                                return retrieved_contents
                            else:
                                logger.error(f"❌ Could not retrieve any file content from filesystem.")
                                logger.error(f"   Found {len(db_files)} files in database, but:")
                                logger.error(f"   - Files not found on filesystem (Cloud Run ephemeral storage)")
                                logger.error(f"   - No embeddings in ChromaDB")
                                logger.error(f"   → Files need to be re-uploaded. This is expected on Cloud Run when container restarts.")
                                # Return empty list - the LLM will inform the user they need to re-upload
                                return []
                        else:
                            logger.info(f"ℹ️  No files in database for user {user_id_str} either")
                    except Exception as db_check_error:
                        logger.error(f"❌ Error checking database files: {db_check_error}", exc_info=True)
                return []
            
            # If db is provided, filter out embeddings for files that no longer exist
            valid_file_ids = None
            file_upload_times = {}  # Initialize here so it's available in outer scope
            if db is not None:
                logger.info(f"Database provided, will filter deleted files for user {user_id_str}")
                try:
                    from sqlalchemy import select
                    from app.models.database import File as FileModel
                    
                    # Get all existing file IDs for this user from database
                    from sqlalchemy.ext.asyncio import AsyncSession
                    
                    # Get file IDs with upload times for ordering (user-scoped now)
                    file_result = await db.execute(
                        select(FileModel.id, FileModel.uploaded_at)
                        .where(FileModel.user_id == user_id)  # Files are user-scoped
                        .order_by(FileModel.uploaded_at.desc())  # Most recent first
                    )
                    file_records = file_result.all()
                    existing_file_ids = {str(fid) for fid, _ in file_records}
                    valid_file_ids = existing_file_ids
                    
                    # Create a map of file_id -> upload_time for prioritization
                    file_upload_times = {str(fid): uploaded_at for fid, uploaded_at in file_records}
                    
                    logger.info(f"Found {len(existing_file_ids)} valid file IDs in database for user {user_id_str}: {existing_file_ids}")
                    
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
                logger.warning(f"No valid files found in ChromaDB for user {user_id_str}")
                return []
            
            # Strategy: Get ALL files for the user, sort by upload time (most recent first)
            # This ensures the most recent file is ALWAYS returned first, regardless of semantic relevance
            # Also use this strategy for generic file requests (summary, analyze, etc.)
            if (valid_file_ids and file_upload_times) or is_generic_file_request:
                # Get ALL files for this user from ChromaDB (not using semantic search)
                # This ensures we have the most recent file even if it's not semantically relevant
                all_user_files = collection.get(
                    where={"user_id": user_id_str}  # Files are user-scoped now
                )
                
                # Filter to only valid files and sort by upload time
                all_ids = all_user_files.get("ids", [])
                all_docs = all_user_files.get("documents", [])
                all_metas = all_user_files.get("metadatas", [])
                
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
                        
                        # For generic file requests, include all files even if we don't have valid_file_ids
                        # Otherwise, only include valid files
                        if is_generic_file_request or (file_id and str(file_id) in valid_file_ids):
                            if file_upload_times and file_id:
                                upload_time = file_upload_times.get(str(file_id), datetime.min.replace(tzinfo=timezone.utc))
                            else:
                                upload_time = datetime.min.replace(tzinfo=timezone.utc)
                            file_items.append((doc, str(file_id) if file_id else f"unknown_{i}", upload_time))
                
                # Sort by upload time ONLY - most recent first (if we have upload times)
                if file_upload_times:
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
            
            # Fallback: if we don't have file_upload_times AND it's not a generic file request, use semantic search
            # For generic file requests, we should still try to get all files even without upload times
            if is_generic_file_request and all_files.get("documents"):
                # For generic requests, return all files even without upload time sorting
                logger.info(f"Generic file request: returning all {len(all_files.get('documents', []))} files without semantic search")
                filtered_docs = []
                for i, doc in enumerate(all_files.get("documents", [])[:n_results]):
                    if len(doc) > 15000:
                        truncated_doc = doc[:15000] + f"\n\n[Content truncated - original was {len(doc)} characters. This is a large file, focusing on the beginning.]"
                        filtered_docs.append(truncated_doc)
                    else:
                        filtered_docs.append(doc)
                return filtered_docs
            
            # Fallback: if we don't have file_upload_times, use semantic search
            # Generate query embedding
            query_embedding = self.embedding_service.generate_embedding(query)
            
            # Query with semantic search (with filtered file_ids if available)
            where_clause = {"user_id": user_id_str}  # Files are user-scoped now
            if valid_file_ids:
                # Note: ChromaDB where clause doesn't support IN directly, so we'll filter after
                where_clause = {"user_id": user_id_str}  # Files are user-scoped now
            
            # Query ALL files for this user to ensure we don't miss the most recent one
            # We'll filter and sort by upload time after
            query_n_results = len(all_files.get("ids", []))  # Get ALL files to ensure we have the most recent
            
            results = collection.query(
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

