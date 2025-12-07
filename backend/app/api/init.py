"""Temporary initialization endpoint for creating admin user and database export"""
from fastapi import APIRouter, HTTPException, status, Depends, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from pydantic import BaseModel, EmailStr
from typing import Optional
import logging
import subprocess
import os
import tempfile
from io import BytesIO
from datetime import datetime

from app.db.database import get_db, engine
from app.models.database import User, Tenant
from app.core.auth import hash_password
from app.core.tenant_context import get_tenant_id
from app.core.user_context import require_admin
from app.core.config import settings
from app.core.dependencies import get_memory_manager
from app.core.memory_manager import MemoryManager
from app.services.embedding_service import EmbeddingService
from app.db.database import AsyncSessionLocal
from uuid import UUID

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/init", tags=["init"])


class CreateAdminRequest(BaseModel):
    email: EmailStr = "admin@example.com"
    password: str = "admin123"
    name: str = "Admin User"


@router.post("/admin")
async def create_admin_user(
    request: CreateAdminRequest,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    """
    Create admin user in the default tenant.
    This endpoint should be called once after initial deployment.
    
    ⚠️ SECURITY: This endpoint is UNPROTECTED by design for initial setup.
    It should be disabled in production after admin user is created.
    """
    # SECURITY: Check if endpoint is enabled via environment variable
    enable_init_admin = os.getenv("ENABLE_INIT_ADMIN", "true").lower() == "true"
    if not enable_init_admin:
        logger.warning(f"⚠️  /api/init/admin endpoint is disabled (ENABLE_INIT_ADMIN=false)")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Init admin endpoint is disabled in production"
        )
    
    # Log all attempts for security monitoring
    logger.warning(f"⚠️  ADMIN CREATION ATTEMPT: email={request.email}, tenant_id={tenant_id}, enable_init_admin={enable_init_admin}")
    
    try:
        # Get default tenant
        result = await db.execute(
            select(Tenant).where(Tenant.schema_name == "tenant_default")
        )
        default_tenant = result.scalar_one_or_none()
        
        if not default_tenant:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Default tenant not found. Run migrations first."
            )
        
        # Check if user already exists
        result = await db.execute(
            select(User).where(
                User.email == request.email,
                User.tenant_id == default_tenant.id
            )
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            # Update password if user exists
            existing_user.password_hash = hash_password(request.password)
            existing_user.role = "admin"
            existing_user.email_verified = True
            existing_user.active = True
            await db.commit()
            await db.refresh(existing_user)
            
            logger.info(f"Updated admin user: {existing_user.email}")
            return {
                "message": "Admin user updated",
                "email": existing_user.email,
                "name": existing_user.name,
                "role": existing_user.role,
                "user_id": str(existing_user.id),
            }
        
        # Create admin user
        password_hash = hash_password(request.password)
        
        admin_user = User(
            tenant_id=default_tenant.id,
            email=request.email,
            name=request.name,
            password_hash=password_hash,
            role="admin",
            email_verified=True,
            active=True,
        )
        
        db.add(admin_user)
        await db.commit()
        await db.refresh(admin_user)
        
        logger.info(f"Admin user created: {admin_user.email}")
        
        return {
            "message": "Admin user created successfully",
            "email": admin_user.email,
            "name": admin_user.name,
            "role": admin_user.role,
            "user_id": str(admin_user.id),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating admin user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating admin user: {str(e)}"
        )


@router.get("/export-database")
async def export_full_database(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Export full database as SQL dump (admin only).
    This endpoint creates a complete pg_dump of the database.
    """
    try:
        logger.info(f"Admin {current_user.email} requested full database export")
        
        # Parse DATABASE_URL to get connection parameters
        db_url = settings.database_url
        
        # Extract components from DATABASE_URL
        # Format: postgresql+asyncpg://user:pass@host:port/dbname
        if "+asyncpg" in db_url:
            db_url = db_url.replace("+asyncpg", "")
        
        # Parse URL
        from urllib.parse import urlparse, unquote
        parsed = urlparse(db_url)
        
        db_host = parsed.hostname
        db_port = parsed.port or 5432
        db_user = parsed.username
        db_pass = unquote(parsed.password) if parsed.password else ""
        db_name = parsed.path.lstrip("/").split("?")[0]  # Remove query params
        
        # Create pg_dump command
        # Use environment variable for password
        env = os.environ.copy()
        env["PGPASSWORD"] = db_pass
        
        dump_command = [
            "pg_dump",
            "-h", db_host,
            "-p", str(db_port),
            "-U", db_user,
            "-d", db_name,
            "--format=plain",
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-privileges",
            "--verbose"
        ]
        
        logger.info(f"Executing pg_dump for {db_user}@{db_host}:{db_port}/{db_name}")
        
        # SECURITY: Add additional validation
        # Only allow export if explicitly enabled (optional additional security)
        enable_db_export = os.getenv("ENABLE_DB_EXPORT", "true").lower() == "true"
        if not enable_db_export:
            logger.warning(f"⚠️  Database export disabled (ENABLE_DB_EXPORT=false)")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Database export is disabled"
            )
        
        # Execute pg_dump
        try:
            result = subprocess.run(
                dump_command,
                env=env,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or "Unknown error"
                logger.error(f"pg_dump failed: {error_msg}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Database export failed: {error_msg}"
                )
            
            dump_content = result.stdout
            
            # Create filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"knowledge_navigator_backup_{timestamp}.sql"
            
            # Return as downloadable file
            return Response(
                content=dump_content,
                media_type="application/sql",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Content-Type": "application/sql"
                }
            )
            
        except subprocess.TimeoutExpired:
            logger.error("pg_dump timed out after 5 minutes")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database export timed out. Database may be too large."
            )
        except FileNotFoundError:
            logger.error("pg_dump command not found")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="pg_dump is not available on this server. Database export not supported."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting database: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error exporting database: {str(e)}"
        )


@router.post("/index-internal-knowledge")
async def index_internal_knowledge(
    current_user: User = Depends(require_admin),
):
    """
    Index all INTERNAL_*.md documents into ChromaDB for self-awareness RAG.
    This endpoint reads all INTERNAL_*.md files from docs/ and indexes them
    into ChromaDB in the internal_knowledge collection.
    
    Admin only endpoint.
    """
    try:
        logger.info(f"Admin {current_user.email} requested internal knowledge indexing")
        
        from pathlib import Path
        from datetime import datetime
        
        # Find docs directory
        # In Docker container: /app/docs/ (project root is /app)
        # In local development: project_root/docs/ (go up from backend/app/api/init.py)
        # Try Docker path first, then local path
        docker_docs_dir = Path("/app/docs")
        if docker_docs_dir.exists():
            docs_dir = docker_docs_dir
        else:
            # Local development path
            project_root = Path(__file__).parent.parent.parent.parent
            docs_dir = project_root / "docs"
        
        if not docs_dir.exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"docs/ directory not found at: {docs_dir}"
            )
        
        # Find all INTERNAL_*.md files
        internal_docs = list(docs_dir.glob("INTERNAL_*.md"))
        
        # Filter out documentation files about indexing/verification
        internal_docs = [
            doc for doc in internal_docs 
            if "INDEXING_STATUS" not in doc.name and "VERIFICATION" not in doc.name
        ]
        
        if not internal_docs:
            return {
                "message": "No INTERNAL_*.md files found",
                "docs_dir": str(docs_dir),
                "indexed": 0,
                "documents": []
            }
        
        logger.info(f"Found {len(internal_docs)} documents to index:")
        for doc in internal_docs:
            logger.info(f"   - {doc.name}")
        
        # Initialize MemoryManager
        # Internal knowledge is shared across all tenants - use default tenant ID
        default_tenant_id = UUID("00000000-0000-0000-0000-000000000000")
        embedding_service = EmbeddingService()
        memory_manager = MemoryManager(
            embedding_service=embedding_service,
            tenant_id=default_tenant_id,
        )
        
        # Chunking configuration
        CHUNK_SIZE = 1000
        CHUNK_OVERLAP = 200
        
        def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
            """Split text into chunks with overlap."""
            chunks = []
            start = 0
            
            while start < len(text):
                end = start + chunk_size
                chunk = text[start:end]
                
                if end < len(text):
                    last_period = chunk.rfind('.')
                    last_newline = chunk.rfind('\n')
                    break_point = max(last_period, last_newline)
                    
                    if break_point > chunk_size * 0.5:
                        chunk = chunk[:break_point + 1]
                        end = start + break_point + 1
                
                chunks.append(chunk.strip())
                start = end - overlap
            
            return chunks
        
        # Index all documents
        total_indexed = 0
        documents_indexed = []
        errors = []
        
        async with AsyncSessionLocal() as db:
            for doc_path in internal_docs:
                filename = doc_path.name
                try:
                    logger.info(f"📄 Indexing {filename}...")
                    
                    # Read document
                    content = doc_path.read_text(encoding="utf-8")
                    
                    if not content.strip():
                        logger.warning(f"⚠️  {filename} is empty, skipping")
                        continue
                    
                    # Chunk the document
                    chunks = chunk_text(content)
                    logger.info(f"   Split into {len(chunks)} chunks")
                    
                    # Get collection (shared)
                    collection = memory_manager._get_collection("internal_knowledge", shared=True)
                    
                    if collection is None:
                        error_msg = f"Could not get internal_knowledge collection"
                        logger.error(f"❌ {error_msg}")
                        errors.append({"document": filename, "error": error_msg})
                        continue
                    
                    # Delete existing chunks for this document first (re-index)
                    try:
                        existing_results = collection.get(
                            where={"document": {"$eq": filename}, "type": {"$eq": "internal_knowledge"}},
                        )
                        existing_ids = existing_results.get("ids", []) if existing_results else []
                        if existing_ids:
                            collection.delete(ids=existing_ids)
                            logger.info(f"   Deleted {len(existing_ids)} existing chunks")
                    except Exception as e:
                        logger.warning(f"   Could not delete existing chunks: {e}")
                    
                    # Index each chunk
                    chunks_indexed = 0
                    for i, chunk in enumerate(chunks):
                        if not chunk.strip():
                            continue
                        
                        chunk_content = f"[Document: {filename}]\n\n{chunk}"
                        embedding = embedding_service.generate_embedding(chunk_content)
                        embedding_id = f"internal_{filename}_{i}_{datetime.now().isoformat()}"
                        
                        collection.add(
                            ids=[embedding_id],
                            embeddings=[embedding],
                            documents=[chunk_content],
                            metadatas=[
                                {
                                    "type": "internal_knowledge",
                                    "document": filename,
                                    "chunk_index": i,
                                    "importance_score": "1.0",
                                }
                            ],
                        )
                        chunks_indexed += 1
                    
                    total_indexed += chunks_indexed
                    documents_indexed.append({
                        "filename": filename,
                        "chunks": chunks_indexed
                    })
                    logger.info(f"✅ Indexed {chunks_indexed} chunks from {filename}")
                    
                except Exception as e:
                    error_msg = f"Error indexing {filename}: {str(e)}"
                    logger.error(f"❌ {error_msg}", exc_info=True)
                    errors.append({"document": filename, "error": error_msg})
        
        logger.info(f"✨ Done! Indexed {total_indexed} chunks total from {len(documents_indexed)} documents")
        
        return {
            "message": f"Successfully indexed {total_indexed} chunks from {len(documents_indexed)} documents",
            "total_chunks": total_indexed,
            "documents": documents_indexed,
            "errors": errors if errors else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error indexing internal knowledge: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error indexing internal knowledge: {str(e)}"
        )

