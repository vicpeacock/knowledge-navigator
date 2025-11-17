from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from typing import Optional
from uuid import UUID
from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    # Pool configuration per evitare esaurimento connessioni
    pool_size=10,  # Numero di connessioni mantenute nel pool
    max_overflow=20,  # Connessioni aggiuntive oltre pool_size
    pool_timeout=30,  # Timeout per ottenere una connessione dal pool
    pool_recycle=3600,  # Ricicla connessioni dopo 1 ora per evitare connessioni stale
    pool_pre_ping=True,  # Verifica che le connessioni siano valide prima di usarle
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db(tenant_schema: Optional[str] = None) -> AsyncSession:
    """
    Dependency for getting database session.
    
    If tenant_schema is provided, sets the search_path to that schema.
    This enables schema-per-tenant isolation.
    
    Args:
        tenant_schema: Optional schema name for tenant isolation
        
    Yields:
        AsyncSession: Database session with optional schema context
    """
    async with AsyncSessionLocal() as session:
        try:
            # Set search_path if tenant schema is provided
            if tenant_schema:
                await session.execute(text(f"SET search_path TO {tenant_schema}, public"))
            yield session
        finally:
            # Reset search_path to default
            if tenant_schema:
                await session.execute(text("SET search_path TO public"))
            await session.close()


async def create_tenant_schema(schema_name: str) -> bool:
    """
    Create a PostgreSQL schema for a tenant.
    
    Args:
        schema_name: Name of the schema to create
        
    Returns:
        bool: True if schema was created, False if it already exists
    """
    async with AsyncSessionLocal() as session:
        try:
            # Check if schema exists
            result = await session.execute(
                text("""
                    SELECT schema_name 
                    FROM information_schema.schemata 
                    WHERE schema_name = :schema_name
                """),
                {"schema_name": schema_name}
            )
            exists = result.scalar_one_or_none()
            
            if exists:
                return False  # Schema already exists
            
            # Create schema
            await session.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            raise e

