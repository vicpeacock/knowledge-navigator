# Multi-Tenant: Sfide e Azioni Urgenti

## Executive Summary

L'architettura attuale di Knowledge Navigator è **single-tenant** (tutti i dati sono globali). Per supportare white-labeling enterprise, dobbiamo implementare **multi-tenancy**. Questo documento analizza le sfide specifiche e identifica cosa fare **SUBITO** per evitare refactoring costosi in futuro.

---

## 🔴 Stato Attuale: Problemi Critici

### 1. Nessun Sistema di Autenticazione/Authorization

**Problema**:
- ❌ Nessun sistema di utenti
- ❌ Nessun sistema di autenticazione (JWT, OAuth, etc.)
- ❌ Nessun controllo accessi
- ❌ Tutte le API sono pubbliche (nessuna protezione)

**Implicazioni**:
- Impossibile distinguere tra clienti
- Impossibile isolare dati
- Security risk critico

**Evidenza**:
```python
# backend/app/api/sessions.py
@router.get("/", response_model=List[Session])
async def list_sessions(...):
    # Restituisce TUTTE le sessioni, senza filtri
    query = select(SessionModel)
    # Nessun filtro per user/tenant
```

---

### 2. Nessun Isolamento Dati

**Problema**:
- ❌ Tutte le sessioni sono globali (nessun `tenant_id` o `user_id`)
- ❌ Query database non filtrano per tenant
- ❌ ChromaDB collections sono globali (non isolate)
- ❌ MemoryLong è cross-session ma non cross-tenant

**Implicazioni**:
- Un cliente può vedere dati di altri clienti
- Impossibile fare white-labeling
- Violazione GDPR/compliance

**Evidenza**:
```python
# backend/app/models/database.py
class Session(Base):
    id = Column(UUID(as_uuid=True), primary_key=True)
    name = Column(String(255), nullable=False)
    # ❌ Manca: tenant_id, user_id
    # ❌ Nessun isolamento
```

```python
# backend/app/core/memory_manager.py
self.long_term_memory_collection = self.chroma_client.get_or_create_collection(
    name="long_term_memory",  # ❌ Collection globale, non per tenant
)
```

---

### 3. Integrations Globali

**Problema**:
- ❌ Integrations (Calendar, Email) sono globali
- ❌ Nessun `tenant_id` o `user_id` nelle integrations
- ❌ Un cliente può vedere integrations di altri

**Evidenza**:
```python
# backend/app/models/database.py
class Integration(Base):
    id = Column(UUID(as_uuid=True), primary_key=True)
    provider = Column(String(50), nullable=False)
    # ❌ Manca: tenant_id, user_id
```

---

### 4. ChromaDB Collections Globali

**Problema**:
- ❌ `file_embeddings_collection` è globale
- ❌ `session_memory_collection` è globale
- ❌ `long_term_memory_collection` è globale
- ❌ Metadata filtering per `session_id` ma non per `tenant_id`

**Implicazioni**:
- Dati di tenant diversi nello stesso collection
- Rischi di cross-contamination
- Impossibile fare backup/restore per tenant

**Evidenza**:
```python
# backend/app/core/memory_manager.py
self.file_embeddings_collection = self.chroma_client.get_or_create_collection(
    name="file_embeddings",  # ❌ Globale
)
# Query usa solo session_id, non tenant_id
results = memory.file_embeddings_collection.query(
    where={"session_id": str(session_id)},  # ❌ Manca tenant_id
)
```

---

### 5. Nessun Tenant Context

**Problema**:
- ❌ Nessun middleware per inject `tenant_id` nelle richieste
- ❌ Nessun dependency injection per tenant context
- ❌ Services non hanno accesso a tenant context

**Implicazioni**:
- Impossibile filtrare automaticamente per tenant
- Ogni query deve esplicitamente filtrare (error-prone)

---

## 🎯 Sfide Specifiche della Fase 0

### Sfida 1: Database Schema Migration

**Cosa serve**:
- Aggiungere `tenant_id` a tutte le tabelle
- Aggiungere `user_id` dove necessario
- Creare tabella `tenants` e `users`
- Migration script per dati esistenti

**Complessità**: 🔴 **ALTA**
- Molte tabelle da modificare
- Dati esistenti da migrare
- Foreign keys da aggiornare
- Index da creare per performance

**Tempo stimato**: 1-2 settimane

---

### Sfida 2: Authentication & Authorization

**Cosa serve**:
- Sistema di autenticazione (JWT o OAuth2)
- User management (create, update, delete users)
- Role-based access control (RBAC)
- Tenant management (create, update, delete tenants)
- API key management per integrazioni

**Complessità**: 🔴 **ALTA**
- Nuovo sistema da zero
- Security critica (non si può sbagliare)
- Integration con frontend
- Session management

**Tempo stimato**: 2-3 settimane

---

### Sfida 3: Tenant Context Middleware

**Cosa serve**:
- Middleware FastAPI per estrarre `tenant_id` da request
- Dependency injection per tenant context
- Validazione tenant esistente e attivo
- Error handling per tenant non valido

**Complessità**: 🟡 **MEDIA**
- Relativamente semplice
- Ma deve essere robusto (security)

**Tempo stimato**: 3-5 giorni

---

### Sfida 4: Query Filtering Automatico

**Cosa serve**:
- Modificare tutte le query per filtrare per `tenant_id`
- Scoped session per SQLAlchemy (auto-filter)
- Validazione che session appartiene a tenant
- Testing per evitare data leaks

**Complessità**: 🔴 **ALTA**
- Molte query da modificare (error-prone)
- Testing estensivo necessario
- Performance impact (index necessari)

**Tempo stimato**: 2-3 settimane

---

### Sfida 5: ChromaDB Multi-Tenant

**Cosa serve**:
- Collection per tenant (o namespace per tenant)
- Metadata filtering per `tenant_id`
- Migration dati esistenti
- Backup/restore per tenant

**Opzioni**:
1. **Collection per tenant**: `file_embeddings_tenant_{id}`
   - ✅ Isolamento perfetto
   - ❌ Molte collections (management complesso)
   
2. **Metadata filtering**: Usare `where={"tenant_id": ...}`
   - ✅ Una collection
   - ⚠️ Isolamento basato su metadata (meno sicuro)

**Raccomandazione**: Collection per tenant per isolamento perfetto.

**Complessità**: 🟡 **MEDIA-ALTA**
- ChromaDB supporta entrambi gli approcci
- Migration dati necessaria

**Tempo stimato**: 1-2 settimane

---

### Sfida 6: Memory Isolation

**Cosa serve**:
- `MemoryLong` deve essere per tenant (non globale)
- `MemoryMedium` già per session (ok, ma session deve avere tenant_id)
- `MemoryShort` già per session (ok)
- Cross-session memory solo dentro stesso tenant

**Complessità**: 🟡 **MEDIA**
- Logic relativamente semplice
- Ma impatta tutto il sistema di memoria

**Tempo stimato**: 1 settimana

---

### Sfida 7: Frontend Multi-Tenant

**Cosa serve**:
- Login/authentication UI
- Tenant selection (se user ha accesso a più tenant)
- Tenant context in tutte le API calls
- White-labeling UI (theme, branding)

**Complessità**: 🟡 **MEDIA**
- UI relativamente semplice
- Ma deve essere user-friendly

**Tempo stimato**: 2-3 settimane

---

### Sfida 8: Resource Quotas & Billing

**Cosa serve**:
- Tracking usage per tenant (API calls, storage, compute)
- Quota enforcement
- Billing integration (opzionale per MVP)
- Usage dashboard

**Complessità**: 🟡 **MEDIA**
- Non critico per MVP
- Può essere aggiunto dopo

**Tempo stimato**: 1-2 settimane (opzionale)

---

## 🚨 Cosa Fare SUBITO (Prima che sia Tardi)

### Azione 1: Aggiungere `tenant_id` ai Modelli Database (URGENTE)

**Perché**: Se aggiungiamo feature nuove senza `tenant_id`, dobbiamo refactorare dopo.

**Cosa fare**:
1. Creare migration per aggiungere `tenant_id` a tutte le tabelle esistenti
2. Per dati esistenti: creare un "default tenant" e assegnare tutto a quello
3. Rendere `tenant_id` NOT NULL dopo migration

**Impatto**: 🟡 **MEDIO** (non rompe funzionalità esistenti se fatto bene)

**Tempo**: 2-3 giorni

**Esempio**:
```python
# Migration: add_tenant_id.py
# 1. Aggiungi colonna tenant_id (nullable)
# 2. Crea default tenant
# 3. Assegna tutti i dati esistenti al default tenant
# 4. Rendi tenant_id NOT NULL
```

---

### Azione 2: Tenant Context Middleware (URGENTE)

**Perché**: Se implementiamo ora, tutte le nuove feature avranno automaticamente tenant context.

**Cosa fare**:
1. Creare middleware che estrae `tenant_id` da header/query param
2. Dependency injection per `get_tenant_context()`
3. Per ora, usare "default tenant" se non specificato (backward compatible)

**Impatto**: 🟢 **BASSO** (non rompe nulla, solo aggiunge context)

**Tempo**: 2-3 giorni

**Esempio**:
```python
# backend/app/core/tenant_context.py
from fastapi import Header, Depends
from uuid import UUID

async def get_tenant_id(
    x_tenant_id: Optional[str] = Header(None)
) -> UUID:
    if x_tenant_id:
        return UUID(x_tenant_id)
    # Backward compatible: default tenant
    return DEFAULT_TENANT_ID

# Usa in endpoints
@router.get("/sessions/")
async def list_sessions(
    tenant_id: UUID = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    # Filtra per tenant
    query = select(SessionModel).where(SessionModel.tenant_id == tenant_id)
```

---

### Azione 3: Modificare Query Esistenti (URGENTE)

**Perché**: Se non filtriamo per tenant, c'è rischio data leak.

**Cosa fare**:
1. Aggiungere filtro `tenant_id` a tutte le query esistenti
2. Validare che `session_id` appartiene a `tenant_id`
3. Testing estensivo

**Impatto**: 🔴 **ALTO** (rompe funzionalità se fatto male)

**Tempo**: 1-2 settimane

**Approccio Incrementale**:
1. **Fase 1**: Aggiungere filtro ma permettere "default tenant" (backward compatible)
2. **Fase 2**: Rendere obbligatorio dopo testing

---

### Azione 4: ChromaDB Collections per Tenant (URGENTE)

**Perché**: Se continuiamo a usare collections globali, migration dopo è costosa.

**Cosa fare**:
1. Modificare `MemoryManager` per creare collections per tenant
2. Pattern: `{collection_name}_tenant_{tenant_id}`
3. Lazy creation (crea collection quando necessario)

**Impatto**: 🟡 **MEDIO** (richiede refactoring MemoryManager)

**Tempo**: 3-5 giorni

**Esempio**:
```python
# backend/app/core/memory_manager.py
class MemoryManager:
    def __init__(self, tenant_id: UUID):
        self.tenant_id = tenant_id
        # Collections per tenant
        self.long_term_memory_collection = self.chroma_client.get_or_create_collection(
            name=f"long_term_memory_tenant_{tenant_id}",
        )
```

---

### Azione 5: Authentication Base (NON URGENTE per MVP)

**Perché**: Per MVP, possiamo usare API keys o tenant ID in header.

**Cosa fare**:
- **MVP**: API key per tenant (semplice)
- **Fase 2**: Full authentication (JWT, OAuth2)

**Impatto**: 🟢 **BASSO** (può essere aggiunto dopo)

**Tempo**: 1 settimana (API keys) o 2-3 settimane (full auth)

---

## 📊 Impatto sulla Roadmap Originale

### Roadmap Attuale (Personal Assistant)

**Fase 1**: Core Integrations ✅
**Fase 2**: Proattività
**Fase 3**: Advanced Features

### Con Multi-Tenant (Enterprise Platform)

**Fase 0**: Multi-Tenant Foundation (2-3 mesi) ⚠️ **NUOVO**
- Database schema migration
- Authentication/Authorization
- Tenant context middleware
- Query filtering
- ChromaDB isolation
- Frontend multi-tenant

**Fase 1**: Core Integrations ✅ (già fatto, ma va adattato per multi-tenant)
- Calendar/Email: già per tenant (grazie a Fase 0)
- Web: già per tenant
- File: già per tenant

**Fase 2**: Proattività (stesso, ma multi-tenant)
**Fase 3**: Advanced Features (stesso, ma multi-tenant)

### Impatto Temporale

**Roadmap Originale**: ~6-9 mesi per Fase 1-3
**Con Multi-Tenant**: +2-3 mesi (Fase 0) = **8-12 mesi totali**

**Ma**: Se facciamo Fase 0 **prima** di aggiungere nuove feature, l'impatto è minimo.

---

## 🎯 Strategia Consigliata

### Opzione 1: Fase 0 PRIMA (Raccomandato)

**Timeline**:
1. **Ora - 2-3 mesi**: Fase 0 (Multi-Tenant Foundation)
2. **Dopo**: Continuare con roadmap originale (Fase 1-3)

**Vantaggi**:
- ✅ Tutte le nuove feature sono automaticamente multi-tenant
- ✅ Nessun refactoring futuro
- ✅ Isolamento dati garantito fin dall'inizio

**Svantaggi**:
- ⚠️ Delay di 2-3 mesi sulla roadmap originale
- ⚠️ Non possiamo aggiungere feature nuove durante Fase 0

---

### Opzione 2: Fase 0 IN PARALLELO (Rischioso)

**Timeline**:
1. **Ora**: Continuare roadmap originale
2. **In parallelo**: Fase 0 (Multi-Tenant)
3. **Dopo**: Merge e refactoring

**Vantaggi**:
- ✅ Non blocca sviluppo feature
- ✅ Progresso su entrambi i fronti

**Svantaggi**:
- ❌ Refactoring costoso dopo
- ❌ Rischio di conflitti
- ❌ Duplicazione lavoro

**Raccomandazione**: ❌ **NON consigliato**

---

### Opzione 3: Fase 0 DOPO (Sconsigliato)

**Timeline**:
1. **Ora**: Continuare roadmap originale
2. **Dopo 6-9 mesi**: Fase 0 (refactoring completo)

**Vantaggi**:
- ✅ Nessun delay iniziale

**Svantaggi**:
- ❌ Refactoring MASSIVO dopo (tutte le feature)
- ❌ Rischio data leaks nel frattempo
- ❌ Costo molto più alto

**Raccomandazione**: ❌ **Sconsigliato**

---

## ✅ Piano d'Azione Immediato

### Settimana 1-2: Preparazione

1. **Analisi completa**:
   - [ ] Audit di tutte le tabelle database
   - [ ] Audit di tutte le query
   - [ ] Audit di ChromaDB collections
   - [ ] Documentazione stato attuale

2. **Design**:
   - [ ] Design database schema (tenant_id, user_id)
   - [ ] Design authentication flow
   - [ ] Design tenant context middleware
   - [ ] Design ChromaDB isolation strategy

### Settimana 3-4: Database Migration

1. **Migration Scripts**:
   - [ ] Creare tabella `tenants`
   - [ ] Creare tabella `users`
   - [ ] Aggiungere `tenant_id` a tutte le tabelle
   - [ ] Creare default tenant
   - [ ] Migrare dati esistenti
   - [ ] Testing migration

### Settimana 5-6: Tenant Context

1. **Middleware**:
   - [ ] Tenant context middleware
   - [ ] Dependency injection
   - [ ] Backward compatibility (default tenant)

2. **Query Filtering**:
   - [ ] Modificare tutte le query per filtrare tenant
   - [ ] Validazione session-tenant ownership
   - [ ] Testing estensivo

### Settimana 7-8: ChromaDB Isolation

1. **MemoryManager Refactoring**:
   - [ ] Collections per tenant
   - [ ] Migration dati ChromaDB
   - [ ] Testing

### Settimana 9-10: Authentication Base

1. **API Keys**:
   - [ ] API key generation per tenant
   - [ ] API key validation middleware
   - [ ] Frontend integration

### Settimana 11-12: Frontend & Testing

1. **Frontend**:
   - [ ] Login/tenant selection UI
   - [ ] API key management UI
   - [ ] Testing end-to-end

2. **Testing**:
   - [ ] Unit tests
   - [ ] Integration tests
   - [ ] Security testing (data leak prevention)

---

## 🚨 Rischi e Mitigazioni

### Rischio 1: Data Leak durante Migration

**Mitigazione**:
- Testing estensivo prima di produzione
- Audit log per tutte le query
- Gradual rollout (un tenant alla volta)

### Rischio 2: Performance Degradation

**Mitigazione**:
- Index su `tenant_id` in tutte le tabelle
- Query optimization
- Caching dove possibile

### Rischio 3: Breaking Changes

**Mitigazione**:
- Backward compatibility (default tenant)
- Feature flags
- Gradual migration

---

## 📝 Conclusioni

**La Fase 0 (Multi-Tenant) è CRITICA** e deve essere fatta **PRIMA** di aggiungere feature enterprise.

**Azioni Urgenti**:
1. ✅ Aggiungere `tenant_id` ai modelli database (2-3 giorni)
2. ✅ Tenant context middleware (2-3 giorni)
3. ✅ Query filtering (1-2 settimane)
4. ✅ ChromaDB isolation (3-5 giorni)

**Timeline Totale Fase 0**: 2-3 mesi

**Impatto Roadmap**: +2-3 mesi, ma evita refactoring costoso futuro.

**Raccomandazione**: Iniziare Fase 0 **SUBITO**, prima di aggiungere feature enterprise.

---

*Documento creato il: 2025-01-XX*
*Versione: 1.0*

