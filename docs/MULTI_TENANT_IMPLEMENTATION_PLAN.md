# Piano di Implementazione Multi-Tenant

## Obiettivo

Implementare multi-tenancy con **schema per cliente** (PostgreSQL schemas separati per tenant) senza rompere funzionalità esistenti.

## Strategia: Refactoring Incrementale

### Principi:
1. ✅ **Backward Compatible**: Default tenant per dati esistenti
2. ✅ **Incrementale**: Step-by-step con test continui
3. ✅ **Non Breaking**: Ogni step mantiene funzionalità esistenti
4. ✅ **Test-Driven**: Test dopo ogni modifica

---

## Fase 1: Preparazione e Analisi (Settimana 1)

### Step 1.1: Audit Completo
- [x] Analisi modelli database esistenti
- [x] Analisi query esistenti
- [x] Analisi ChromaDB collections
- [x] Analisi integrazioni

### Step 1.2: Design Schema Multi-Tenant
- [ ] Design tabelle `tenants` e `users`
- [ ] Design schema PostgreSQL per tenant
- [ ] Design tenant context middleware
- [ ] Design ChromaDB isolation strategy

---

## Fase 2: Database Schema (Settimana 2-3)

### Step 2.1: Creare Modelli Tenant e User

**File**: `backend/app/models/database.py`

```python
class Tenant(Base):
    __tablename__ = "tenants"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    schema_name = Column(String(63), nullable=False, unique=True)  # PostgreSQL schema name
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    metadata = Column(JSONB, default={})


class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    email = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    metadata = Column(JSONB, default={})
    
    # Unique constraint: email per tenant
    __table_args__ = (
        UniqueConstraint('tenant_id', 'email', name='uq_user_tenant_email'),
    )
```

**Approccio**: 
- Creare modelli senza modificare esistenti
- Migration separata per nuove tabelle
- **NON toccare** tabelle esistenti ancora

---

### Step 2.2: Migration per Tenant e User

**File**: `backend/alembic/versions/add_tenants_users.py`

```python
def upgrade():
    # Create tenants table
    op.create_table(
        'tenants',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('schema_name', sa.String(63), nullable=False),
        sa.Column('active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('metadata', postgresql.JSONB, default={}),
    )
    op.create_unique_constraint('uq_tenants_name', 'tenants', ['name'])
    op.create_unique_constraint('uq_tenants_schema', 'tenants', ['schema_name'])
    
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('metadata', postgresql.JSONB, default={}),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
    )
    op.create_unique_constraint('uq_user_tenant_email', 'users', ['tenant_id', 'email'])
    
    # Create default tenant
    default_tenant_id = uuid.uuid4()
    op.execute(f"""
        INSERT INTO tenants (id, name, schema_name, active)
        VALUES ('{default_tenant_id}', 'Default Tenant', 'tenant_default', true)
    """)
```

**Test**: Verificare che migration funzioni e crei default tenant.

---

### Step 2.3: Aggiungere tenant_id alle Tabelle Esistenti

**Approccio Incrementale**:

1. **Fase A**: Aggiungere colonna `tenant_id` (nullable)
2. **Fase B**: Assegnare default tenant a tutti i dati esistenti
3. **Fase C**: Rendere `tenant_id` NOT NULL
4. **Fase D**: Aggiungere foreign key e index

**File**: `backend/alembic/versions/add_tenant_id_to_tables.py`

```python
def upgrade():
    # Step 1: Add tenant_id column (nullable) to all tables
    tables = ['sessions', 'messages', 'files', 'memory_medium', 'memory_long', 
              'integrations', 'notifications']
    
    for table in tables:
        op.add_column(table, sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True))
    
    # Step 2: Get default tenant ID
    default_tenant_id = op.execute("SELECT id FROM tenants WHERE schema_name = 'tenant_default'").scalar()
    
    # Step 3: Assign default tenant to all existing data
    for table in tables:
        op.execute(f"UPDATE {table} SET tenant_id = '{default_tenant_id}' WHERE tenant_id IS NULL")
    
    # Step 4: Make tenant_id NOT NULL
    for table in tables:
        op.alter_column(table, 'tenant_id', nullable=False)
    
    # Step 5: Add foreign keys
    for table in tables:
        op.create_foreign_key(
            f'fk_{table}_tenant',
            table, 'tenants',
            ['tenant_id'], ['id']
        )
    
    # Step 6: Add indexes for performance
    for table in tables:
        op.create_index(f'ix_{table}_tenant_id', table, ['tenant_id'])
```

**Test**: 
- Verificare che tutti i dati esistenti abbiano `tenant_id`
- Verificare che query esistenti funzionino ancora

---

## Fase 3: Tenant Context e Middleware (Settimana 3-4)

### Step 3.1: Tenant Context Service

**File**: `backend/app/core/tenant_context.py`

```python
from typing import Optional
from uuid import UUID
from fastapi import Header, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.models.database import Tenant

# Default tenant ID (per backward compatibility)
DEFAULT_TENANT_ID: Optional[UUID] = None  # Will be set on startup


async def get_tenant_id(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> UUID:
    """
    Extract tenant_id from request headers.
    Priority: X-Tenant-ID > X-API-Key > Default Tenant
    """
    # TODO: Implement API key lookup (Step 3.2)
    if x_tenant_id:
        try:
            tenant_id = UUID(x_tenant_id)
            # Validate tenant exists and is active
            result = await db.execute(
                select(Tenant).where(
                    Tenant.id == tenant_id,
                    Tenant.active == True
                )
            )
            tenant = result.scalar_one_or_none()
            if not tenant:
                raise HTTPException(status_code=404, detail="Tenant not found or inactive")
            return tenant_id
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid tenant ID format")
    
    # Backward compatibility: use default tenant
    if DEFAULT_TENANT_ID:
        return DEFAULT_TENANT_ID
    
    # Fallback: get default tenant from database
    result = await db.execute(
        select(Tenant).where(Tenant.schema_name == "tenant_default")
    )
    default_tenant = result.scalar_one_or_none()
    if not default_tenant:
        raise HTTPException(status_code=500, detail="Default tenant not configured")
    
    return default_tenant.id


class TenantContext:
    """Context object for current tenant"""
    
    def __init__(self, tenant_id: UUID, schema_name: str):
        self.tenant_id = tenant_id
        self.schema_name = schema_name


async def get_tenant_context(
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    """Get full tenant context including schema name"""
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    
    return TenantContext(
        tenant_id=tenant.id,
        schema_name=tenant.schema_name
    )
```

---

### Step 3.2: Modificare get_db() per Schema Routing

**File**: `backend/app/db/database.py`

**Approccio**: 
- Mantenere `get_db()` esistente per backward compatibility
- Creare `get_db_for_tenant()` per multi-tenant
- Usare `search_path` PostgreSQL per schema routing

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import event
from app.core.config import settings
from app.core.tenant_context import TenantContext, get_tenant_context

# Existing engine (for default/public schema)
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
)

# Session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """
    Default database session (backward compatible).
    Uses default tenant schema.
    """
    async with async_session_maker() as session:
        # Set search_path to default tenant schema
        await session.execute(text("SET search_path TO tenant_default, public"))
        yield session
        await session.commit()


async def get_db_for_tenant(
    tenant_context: TenantContext = Depends(get_tenant_context),
) -> AsyncSession:
    """
    Database session for specific tenant.
    Uses tenant-specific schema.
    """
    async with async_session_maker() as session:
        # Set search_path to tenant schema
        schema_name = tenant_context.schema_name
        await session.execute(text(f"SET search_path TO {schema_name}, public"))
        yield session
        await session.commit()
```

**Nota**: PostgreSQL `search_path` permette di usare lo stesso database con schemi separati.

---

### Step 3.3: Modificare Endpoints per Usare Tenant Context

**Approccio Incrementale**:

1. **Fase A**: Aggiungere `tenant_context` dependency (opzionale)
2. **Fase B**: Filtrare query per `tenant_id` quando disponibile
3. **Fase C**: Rendere obbligatorio dopo testing

**Esempio**: `backend/app/api/sessions.py`

```python
from app.core.tenant_context import get_tenant_context, TenantContext

@router.get("/", response_model=List[Session])
async def list_sessions(
    status: Optional[str] = None,
    tenant_context: Optional[TenantContext] = Depends(get_tenant_context, use_cache=False),
    db: AsyncSession = Depends(get_db_for_tenant),
):
    """List all sessions for current tenant"""
    query = select(SessionModel).where(SessionModel.tenant_id == tenant_context.tenant_id)
    
    if status:
        query = query.where(SessionModel.status == status)
    
    query = query.order_by(SessionModel.updated_at.desc())
    result = await db.execute(query)
    sessions = result.scalars().all()
    
    return [Session(...) for s in sessions]
```

**Test**: 
- Verificare che endpoint funzionino con default tenant
- Verificare che filtri per tenant_id funzionino

---

## Fase 4: ChromaDB Isolation (Settimana 4-5)

### Step 4.1: Refactoring MemoryManager

**File**: `backend/app/core/memory_manager.py`

**Approccio**:
- Modificare `__init__` per accettare `tenant_id`
- Creare collections per tenant: `{collection_name}_tenant_{tenant_id}`
- Lazy creation (crea collection quando necessario)

```python
class MemoryManager:
    def __init__(self, tenant_id: UUID):
        self.tenant_id = tenant_id
        self.chroma_client = chromadb.HttpClient(...)
        
        # Collections per tenant
        self.file_embeddings_collection = self.chroma_client.get_or_create_collection(
            name=f"file_embeddings_tenant_{tenant_id}",
            metadata={"hnsw:space": "cosine"},
        )
        self.session_memory_collection = self.chroma_client.get_or_create_collection(
            name=f"session_memory_tenant_{tenant_id}",
            metadata={"hnsw:space": "cosine"},
        )
        self.long_term_memory_collection = self.chroma_client.get_or_create_collection(
            name=f"long_term_memory_tenant_{tenant_id}",
            metadata={"hnsw:space": "cosine"},
        )
```

---

### Step 4.2: Modificare Dependency Injection

**File**: `backend/app/core/dependencies.py`

```python
from app.core.tenant_context import get_tenant_context, TenantContext
from app.core.memory_manager import MemoryManager

def get_memory_manager(
    tenant_context: TenantContext = Depends(get_tenant_context),
) -> MemoryManager:
    """Get MemoryManager for current tenant"""
    return MemoryManager(tenant_id=tenant_context.tenant_id)
```

---

## Fase 5: Query Filtering (Settimana 5-6)

### Step 5.1: Audit e Modifica Query

**File**: `backend/app/api/sessions.py`

**Tutte le query devono filtrare per `tenant_id`**:

```python
# PRIMA (single-tenant)
query = select(SessionModel).where(SessionModel.id == session_id)

# DOPO (multi-tenant)
query = select(SessionModel).where(
    SessionModel.id == session_id,
    SessionModel.tenant_id == tenant_context.tenant_id
)
```

**Checklist**:
- [ ] `backend/app/api/sessions.py` - tutte le query
- [ ] `backend/app/api/files.py` - tutte le query
- [ ] `backend/app/api/memory.py` - tutte le query
- [ ] `backend/app/api/notifications.py` - tutte le query
- [ ] `backend/app/api/integrations/*.py` - tutte le query
- [ ] `backend/app/services/*.py` - tutte le query che accedono a DB

**Test**: 
- Verificare che ogni endpoint filtri correttamente
- Test di isolamento (simulare 2 tenant)

---

## Fase 6: Authentication Base (Settimana 6-7)

### Step 6.1: API Key Management

**File**: `backend/app/models/database.py`

```python
class ApiKey(Base):
    __tablename__ = "api_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    key_hash = Column(String(255), nullable=False, unique=True)  # SHA-256 hash
    name = Column(String(255), nullable=True)  # User-friendly name
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)
```

**File**: `backend/app/core/tenant_context.py`

```python
async def get_tenant_id_from_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> Optional[UUID]:
    """Lookup tenant_id from API key"""
    if not x_api_key:
        return None
    
    # Hash API key
    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    
    # Lookup in database
    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_hash == key_hash,
            ApiKey.active == True
        )
    )
    api_key = result.scalar_one_or_none()
    
    if api_key:
        # Update last_used_at
        api_key.last_used_at = datetime.now(timezone.utc)
        await db.commit()
        return api_key.tenant_id
    
    return None
```

---

## Fase 7: Testing e Validazione (Settimana 7-8)

### Step 7.1: Unit Tests
- [ ] Test tenant context middleware
- [ ] Test query filtering
- [ ] Test ChromaDB isolation
- [ ] Test API key authentication

### Step 7.2: Integration Tests
- [ ] Test isolamento dati (2 tenant non vedono dati dell'altro)
- [ ] Test backward compatibility (default tenant)
- [ ] Test performance (query con index)

### Step 7.3: Security Tests
- [ ] Test data leak prevention
- [ ] Test unauthorized access
- [ ] Test API key validation

---

## Checklist Finale

### Backward Compatibility
- [x] Default tenant per dati esistenti
- [x] Endpoint esistenti funzionano senza modifiche frontend
- [x] Dati esistenti accessibili

### Multi-Tenant
- [ ] Tenant isolation garantito
- [ ] Query filtrano per tenant_id
- [ ] ChromaDB collections per tenant
- [ ] Authentication funziona

### Performance
- [ ] Index su tenant_id in tutte le tabelle
- [ ] Query performance accettabile
- [ ] ChromaDB performance accettabile

---

## Rischi e Mitigazioni

### Rischio 1: Breaking Changes
**Mitigazione**: 
- Backward compatibility con default tenant
- Feature flags per nuove funzionalità
- Testing estensivo

### Rischio 2: Data Leak
**Mitigazione**:
- Query sempre filtrano per tenant_id
- Testing isolamento
- Audit log

### Rischio 3: Performance
**Mitigazione**:
- Index su tenant_id
- Query optimization
- Monitoring

---

*Documento creato il: 2025-01-XX*
*Versione: 1.0*

