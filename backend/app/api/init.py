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

