# Multi-Tenant Implementation - Documentazione Completa

## 📋 Indice

1. [Panoramica](#panoramica)
2. [Architettura](#architettura)
3. [Database Schema](#database-schema)
4. [Tenant Context](#tenant-context)
5. [Query Filtering](#query-filtering)
6. [Integrations](#integrations)
7. [Testing](#testing)
8. [Backward Compatibility](#backward-compatibility)
9. [Prossimi Passi](#prossimi-passi)

---

## Panoramica

L'implementazione multi-tenant permette al sistema di servire multiple organizzazioni (tenant) da una singola istanza, garantendo:

- **Isolamento dati**: Ogni tenant vede solo i propri dati
- **Schema per cliente**: Supporto per schemi PostgreSQL separati (futuro)
- **Backward compatibility**: I dati esistenti sono automaticamente migrati al default tenant
- **Scalabilità**: Pronto per espansione multi-tenant reale

---

## Architettura

### Componenti Principali

1. **Tenant Model** (`app/models/database.py`)
   - Tabella `tenants` con informazioni base
   - Campo `schema_name` per supporto schema per tenant (futuro)

2. **User Model** (`app/models/database.py`)
   - Tabella `users` collegata a `tenants`
   - Supporto per autenticazione multi-tenant (futuro)

3. **Tenant Context** (`app/core/tenant_context.py`)
   - Dependency `get_tenant_id()` per estrarre tenant da request
   - Inizializzazione automatica del default tenant
   - Supporto per API keys (futuro)

4. **Query Filtering**
   - Tutte le query filtrano automaticamente per `tenant_id`
   - Verifica che le risorse appartengano al tenant corrente

---

## Database Schema

### Tabelle Modificate

Tutte le tabelle esistenti sono state modificate per includere `tenant_id`:

```sql
-- Esempio: sessions
ALTER TABLE sessions ADD COLUMN tenant_id UUID NOT NULL;
ALTER TABLE sessions ADD CONSTRAINT fk_sessions_tenant_id 
    FOREIGN KEY (tenant_id) REFERENCES tenants(id);
CREATE INDEX ix_sessions_tenant_id ON sessions(tenant_id);
```

### Tabelle Aggiunte

#### `tenants`
```sql
CREATE TABLE tenants (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    schema_name VARCHAR(63) NOT NULL UNIQUE,
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);
```

#### `users`
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    UNIQUE(tenant_id, email)
);
```

### Migrations

Le migrations sono state create in `backend/alembic/versions/`:

1. **`add_tenants_users.py`**: Crea tabelle `tenants` e `users`, inserisce default tenant
2. **`add_tenant_id_to_tables.py`**: Aggiunge `tenant_id` a tutte le tabelle esistenti, migra dati

---

## Tenant Context

### Dependency Injection

Tutti gli endpoint API usano `get_tenant_id()` come dependency:

```python
from app.core.tenant_context import get_tenant_id

@router.get("/sessions")
async def get_sessions(
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
    # Query automaticamente filtrata per tenant_id
    result = await db.execute(
        select(Session).where(Session.tenant_id == tenant_id)
    )
    return result.scalars().all()
```

### Priorità di Determinazione Tenant

1. **Header `X-Tenant-ID`**: Per autenticazione futura
2. **API Key**: Per autenticazione programmatica (futuro)
3. **Default Tenant**: Per backward compatibility

### Default Tenant

Il default tenant viene creato automaticamente alla prima migrazione:
- **Name**: "Default Tenant"
- **Schema Name**: "tenant_default"
- **ID**: Generato automaticamente

Tutti i dati esistenti vengono migrati al default tenant durante la migration.

---

## Query Filtering

### Pattern Standard

Tutte le query seguono questo pattern:

```python
# ✅ CORRETTO
result = await db.execute(
    select(Model).where(
        Model.id == resource_id,
        Model.tenant_id == tenant_id  # Sempre presente
    )
)

# ❌ SBAGLIATO (manca filtro tenant)
result = await db.execute(
    select(Model).where(Model.id == resource_id)
)
```

### Verifica Appartenenza

Prima di operazioni su risorse, verificare sempre l'appartenenza:

```python
# Verifica che la sessione appartenga al tenant
result = await db.execute(
    select(Session).where(
        Session.id == session_id,
        Session.tenant_id == tenant_id
    )
)
session = result.scalar_one_or_none()
if not session:
    raise HTTPException(status_code=404, detail="Session not found")
```

### Creazione Risorse

Tutte le nuove risorse devono includere `tenant_id`:

```python
# ✅ CORRETTO
session = Session(
    name="New Session",
    tenant_id=tenant_id,  # Sempre presente
    # ... altri campi
)

# ❌ SBAGLIATO (manca tenant_id)
session = Session(
    name="New Session",
    # tenant_id mancante!
)
```

---

## Integrations

### Filtri Applicati

Tutti gli endpoint in `app/api/integrations/` filtrano per `tenant_id`:

#### Calendars (`calendars.py`)
- ✅ `/oauth/authorize` - Filtra per tenant
- ✅ `/oauth/callback` - Crea/aggiorna integration con tenant_id
- ✅ `/events` - Filtra integration per tenant
- ✅ `/query` - Filtra integration per tenant
- ✅ `/integrations` - Lista solo integrations del tenant
- ✅ `/integrations/{id}` - Delete solo se appartiene al tenant

#### Emails (`emails.py`)
- ✅ `/oauth/authorize` - Filtra per tenant
- ✅ `/oauth/callback` - Crea/aggiorna integration con tenant_id
- ✅ `/messages` - Filtra integration per tenant
- ✅ `/summarize` - Filtra integration per tenant
- ✅ `/integrations` - Lista solo integrations del tenant
- ✅ `/integrations/{id}` - Delete solo se appartiene al tenant

#### MCP (`mcp.py`)
- ✅ `/connect` - Crea integration con tenant_id
- ✅ `/{id}/tools` - Filtra integration per tenant
- ✅ `/{id}/tools/select` - Filtra e aggiorna solo integration del tenant
- ✅ `/integrations` - Lista solo integrations del tenant
- ✅ `/integrations/{id}` - Delete solo se appartiene al tenant
- ✅ `/{id}/debug` - Filtra integration per tenant
- ✅ `/{id}/test` - Filtra integration per tenant

### Pattern UPDATE

Anche le query UPDATE devono filtrare per tenant:

```python
# ✅ CORRETTO
await db.execute(
    update(IntegrationModel)
    .where(
        IntegrationModel.id == integration_id,
        IntegrationModel.tenant_id == tenant_id  # Sempre presente
    )
    .values(session_metadata=new_metadata)
)

# ❌ SBAGLIATO (manca filtro tenant)
await db.execute(
    update(IntegrationModel)
    .where(IntegrationModel.id == integration_id)
    .values(session_metadata=new_metadata)
)
```

---

## Testing

### Suite di Test

La suite completa di test si trova in `backend/scripts/test_multi_tenant_complete.py`.

#### Test Inclusi

1. **Tenant Initialization**
   - Verifica che il default tenant sia inizializzato
   - Verifica schema_name corretto

2. **Data Integrity**
   - Verifica che nessun record abbia `tenant_id` NULL
   - Conta record per tabella

3. **Tenant Isolation**
   - Verifica che i dati siano isolati per tenant
   - Verifica che i messaggi appartengano alle sessioni corrette

4. **Query Filtering**
   - Verifica che le query filtrino correttamente
   - Testa tutte le tabelle principali

5. **Backward Compatibility**
   - Verifica che tutti i dati esistenti siano migrati
   - Verifica che non ci siano dati orfani

6. **Foreign Key Constraints**
   - Verifica che tutti i `tenant_id` siano validi
   - Verifica integrità referenziale

7. **Index Performance**
   - Verifica che le query con `tenant_id` siano efficienti
   - Testa performance degli indici

### Esecuzione Test

```bash
cd backend
source venv/bin/activate  # o .venv/bin/activate
python3 scripts/test_multi_tenant_complete.py
```

### Test Rapidi

Per test rapidi, usa:
```bash
python3 scripts/test_multi_tenant.py  # Test base
python3 scripts/test_multi_tenant_e2e.py  # Test end-to-end
```

---

## Backward Compatibility

### Migrazione Dati

Tutti i dati esistenti vengono automaticamente migrati al default tenant durante la migration `add_tenant_id_to_tables.py`:

```python
# Per ogni tabella
UPDATE table_name
SET tenant_id = (SELECT id FROM tenants WHERE schema_name = 'tenant_default' LIMIT 1)
WHERE tenant_id IS NULL;
```

### Compatibilità API

- Tutti gli endpoint esistenti continuano a funzionare
- Il default tenant viene usato automaticamente se non specificato
- Nessuna modifica richiesta al frontend (per ora)

---

## Prossimi Passi

### TODO Immediati

- [x] ✅ Database schema e migrations
- [x] ✅ Tenant context middleware
- [x] ✅ Query filtering per tutte le tabelle
- [x] ✅ Integrations filtering
- [x] ✅ Testing completo
- [x] ✅ Documentazione

### TODO Futuri

- [ ] **ChromaDB Isolation**: Collections separate per tenant
- [ ] **Schema per Tenant**: Supporto per schemi PostgreSQL separati
- [ ] **Autenticazione**: API keys per tenant, JWT con tenant claim
- [ ] **User Management**: Gestione utenti per tenant
- [ ] **Tenant Admin**: Interfaccia per gestione tenant
- [ ] **Billing**: Integrazione con sistema di billing
- [ ] **Rate Limiting**: Limiti per tenant
- [ ] **Monitoring**: Metriche per tenant

### ChromaDB Isolation (mt-8)

Attualmente ChromaDB usa collections condivise. Per isolamento completo:

1. Creare collections per tenant: `memory_long_tenant_{tenant_id}`
2. Modificare `MemoryManager` per selezionare collection basata su tenant
3. Migrare embeddings esistenti al default tenant collection

### Autenticazione (mt-9)

Per autenticazione multi-tenant:

1. **API Keys**: Tabella `api_keys` con `tenant_id`
2. **JWT**: Includere `tenant_id` nel claim
3. **OAuth**: Supporto per OAuth con tenant context

---

## File Modificati

### Database Models
- `backend/app/models/database.py` - Aggiunti modelli `Tenant` e `User`, `tenant_id` a tutti i modelli

### Migrations
- `backend/alembic/versions/add_tenants_users.py` - Crea tabelle tenant/user
- `backend/alembic/versions/add_tenant_id_to_tables.py` - Aggiunge tenant_id a tutte le tabelle

### Core
- `backend/app/core/tenant_context.py` - Tenant context e dependency injection

### API Endpoints
- `backend/app/api/sessions.py` - Filtri tenant su tutti gli endpoint
- `backend/app/api/files.py` - Filtri tenant su tutti gli endpoint
- `backend/app/api/notifications.py` - Filtri tenant su tutti gli endpoint
- `backend/app/api/memory.py` - Filtri tenant su tutti gli endpoint
- `backend/app/api/integrations/calendars.py` - Filtri tenant su tutti gli endpoint
- `backend/app/api/integrations/emails.py` - Filtri tenant su tutti gli endpoint
- `backend/app/api/integrations/mcp.py` - Filtri tenant su tutti gli endpoint

### Services
- `backend/app/services/notification_service.py` - Supporto tenant_id
- `backend/app/services/background_agent.py` - Estrae tenant_id da session
- `backend/app/services/task_dispatcher.py` - Filtri tenant su query
- `backend/app/core/memory_manager.py` - Supporto tenant_id per long-term memory

### Agents
- `backend/app/agents/main_agent.py` - Supporto tenant_id
- `backend/app/agents/langgraph_app.py` - Estrae tenant_id da session

### Testing
- `backend/scripts/test_migration.py` - Test migrazione base
- `backend/scripts/test_multi_tenant.py` - Test multi-tenant base
- `backend/scripts/test_multi_tenant_e2e.py` - Test end-to-end
- `backend/scripts/test_multi_tenant_complete.py` - Suite completa di test

---

## Conclusioni

L'implementazione multi-tenant è completa e testata. Il sistema:

✅ Isola correttamente i dati tra tenant  
✅ Mantiene backward compatibility  
✅ Filtra tutte le query per tenant_id  
✅ Supporta integrations multi-tenant  
✅ Include suite completa di test  

Il sistema è pronto per:
- Espansione multi-tenant reale
- Implementazione autenticazione
- Isolamento ChromaDB (futuro)
- Schema per tenant (futuro)

---

**Data**: 2025-11-15  
**Versione**: 1.0  
**Autore**: AI Assistant

