# Analisi Architettura Knowledge Navigator

## 📋 Executive Summary

**Knowledge Navigator** è un sistema multi-agente per gestione della conoscenza e automazione, costruito con FastAPI (backend) e Next.js/React (frontend). Il sistema implementa un'architettura complessa con memoria multi-livello, integrazioni esterne, sistema multi-tenant e observability completa.

**Data Analisi**: 2025-11-17  
**Versione**: 0.1.0

---

## 🏗️ Architettura Generale

### Stack Tecnologico

**Backend:**
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 16 (dati strutturati) + ChromaDB (vector database per RAG)
- **LLM**: Ollama/llama.cpp (locale) con supporto per Gemini (futuro)
- **Agent Framework**: LangGraph per orchestrazione multi-agente
- **Observability**: OpenTelemetry (tracing) + Prometheus (metrics)
- **Autenticazione**: JWT con refresh tokens

**Frontend:**
- **Framework**: Next.js 14+ (React)
- **Styling**: Tailwind CSS
- **State Management**: React Context API
- **HTTP Client**: Axios con interceptors per tracing

**Infrastruttura:**
- **Container**: Docker Compose (PostgreSQL, ChromaDB)
- **Process Management**: Script bash per gestione servizi
- **Background Jobs**: Task queue asincrona

---

## 🎯 Componenti Principali

### 1. Backend FastAPI (`backend/app/main.py`)

#### Struttura Applicazione

```python
FastAPI App
├── Lifespan Management
│   ├── Startup: Inizializza tracing, metrics, clients, default tenant
│   └── Shutdown: Chiude connessioni Ollama/MCP
├── Middleware Stack
│   ├── CORS Middleware
│   └── Observability Middleware (tracing + metrics)
└── API Routers
    ├── /api/sessions - Gestione sessioni chat
    ├── /api/files - Upload e gestione file
    ├── /api/memory - Accesso memoria multi-livello
    ├── /api/tools - Lista tools disponibili
    ├── /api/web - Ricerca web e navigazione
    ├── /api/notifications - Sistema notifiche
    ├── /api/integrations/calendars - Google Calendar
    ├── /api/integrations/emails - Gmail
    ├── /api/integrations/mcp - MCP Gateway (browser tools)
    ├── /api/auth - Autenticazione JWT
    ├── /api/users - Gestione utenti
    └── /metrics - Endpoint Prometheus
```

#### Dependency Injection

Il sistema usa FastAPI dependencies per:
- **Database**: `get_db()` - AsyncSession PostgreSQL
- **Tenant Context**: `get_tenant_id()` - Estrae tenant da header/API key/default
- **User Context**: `get_current_user()` - Estrae utente da JWT token
- **Clients**: `get_ollama_client()`, `get_mcp_client()`, `get_memory_manager()`
- **Services**: `get_task_queue()`, `get_background_task_manager()`

---

### 2. Sistema Multi-Agente (LangGraph)

#### Architettura Agent (`backend/app/agents/langgraph_app.py`)

Il sistema usa **LangGraph** per orchestrazione multi-agente:

```
LangGraph State Machine
│
├── Event Handler
│   └── Processa richiesta utente iniziale
│
├── Orchestrator
│   └── Decide quale agent/tool usare
│
├── Tool Loop
│   ├── Esegue tool calls (iterativo)
│   └── Gestisce risposte LLM con tool calling
│
├── Planner (opzionale)
│   └── Genera piano multi-step per task complessi
│
├── Knowledge Agent
│   └── Recupera e integra memoria
│
├── Integrity Agent
│   └── Verifica contraddizioni nella memoria
│
├── Notification Collector
│   └── Raccoglie notifiche da vari agenti
│
└── Response Formatter
    └── Formatta risposta finale per utente
```

#### Flow di Esecuzione

1. **User Input** → `chat()` endpoint in `sessions.py`
2. **Context Assembly**:
   - System prompt
   - Session history (ottimizzata con `ConversationSummarizer`)
   - Retrieved memory (short/medium/long-term)
   - File content
   - Tool descriptions
3. **LangGraph Execution**:
   - State machine esegue agenti in sequenza
   - Tool calls iterativi fino a completamento
   - Background tasks per memory extraction
4. **Response**:
   - Streaming response al frontend
   - Salvataggio messaggi in database
   - Background processing (memory extraction, integrity checks)

---

### 3. Sistema Memoria Multi-Livello (`backend/app/core/memory_manager.py`)

#### Architettura Memoria

```
Memory System
│
├── Short-Term Memory (TTL: 1 ora)
│   ├── Storage: In-memory cache + PostgreSQL
│   ├── Scope: Session-specific
│   └── Use Case: Context immediato conversazione
│
├── Medium-Term Memory (TTL: 30 giorni)
│   ├── Storage: PostgreSQL + ChromaDB (embeddings)
│   ├── Scope: Session-specific
│   └── Use Case: Informazioni rilevanti per sessione
│
└── Long-Term Memory (Persistente)
    ├── Storage: PostgreSQL + ChromaDB (embeddings)
    ├── Scope: Cross-session, user-level
    └── Use Case: Conoscenza persistente utente
```

#### Memory Operations

**Retrieval:**
- Semantic search con ChromaDB (cosine similarity)
- Query-based filtering
- Multi-tenant isolation (collections per tenant)

**Storage:**
- Automatic extraction da conversazioni (`ConversationLearner`)
- Manual storage da tool outputs
- Background consolidation (`MemoryConsolidator`)

**Consolidation:**
- Deduplicazione (similarity threshold 0.85)
- Merge memorie simili
- Contradiction detection (`SemanticIntegrityChecker`)

#### Context Engineering

Il sistema implementa principi di Context Engineering:
- **Dynamic Context Assembly**: Contesto assemblato dinamicamente per ogni turno
- **Context Window Management**: Ottimizzazione quando supera limiti (riassunto messaggi vecchi)
- **Multi-Level Retrieval**: Short/medium/long-term memory recuperate e combinate

---

### 4. Tool System (`backend/app/core/tool_manager.py`)

#### Categorie Tools

**Base Tools (Built-in):**
- `get_calendar_events` - Google Calendar integration
- `get_emails` - Gmail integration
- `summarize_emails` - AI email summarization
- `web_search` - Ricerca web Ollama API (solo per Ollama)
- `web_fetch` - Fetch contenuto pagina web (solo per Ollama)
- `customsearch_search` - Ricerca web Google Custom Search API (solo per Gemini)

**MCP Tools (Dynamic):**
- Browser tools (Playwright): `navigate`, `snapshot`, `click`, `evaluate`, etc.
- Tools da MCP servers esterni (configurabili per utente)

**Tool Execution Flow:**

```
LLM Request
│
├── Tool Calling Detection
│   └── LLM decide se/usare quale tool
│
├── Tool Execution
│   ├── Base tools → Direct execution
│   ├── MCP tools → MCP Gateway → Playwright/Docker
│   └── Integration tools → OAuth2 → External APIs
│
├── Result Processing
│   └── Tool output aggiunto al context
│
└── Iteration
    └── LLM continua fino a completamento
```

#### Tool Preferences

- Utenti possono selezionare quali MCP tools abilitare
- Preferenze salvate per utente (`user_tool_preferences`)
- Tools filtrati prima di essere esposti all'LLM

---

### 5. Integrazioni Esterne

#### Google Calendar (`backend/app/api/integrations/calendars.py`)

**Flow:**
1. OAuth2 authorization → Google OAuth
2. Token storage → Database (encrypted)
3. Query events → Google Calendar API
4. Natural language parsing → `DateParser` per query come "domani", "questa settimana"
5. Tool calling → `get_calendar_events` tool

**Isolamento:**
- Integration per tenant + user
- Token OAuth isolati per utente

#### Gmail (`backend/app/api/integrations/emails.py`)

**Flow:**
1. OAuth2 authorization → Google OAuth
2. Token storage → Database (encrypted)
3. Read emails → Gmail API con query filters
4. Email indexing → Automatico in long-term memory
5. Tool calling → `get_emails`, `summarize_emails` tools

**Features:**
- Query Gmail filters (`is:unread`, `from:`, etc.)
- Email summarization con LLM
- Automatic indexing in ChromaDB

#### MCP Gateway (`backend/app/api/integrations/mcp.py`)

**Architettura:**
- Docker container con MCP Gateway
- Playwright per browser automation
- Tools esposti dinamicamente da MCP servers

**Browser Tools:**
- `navigate` - Naviga a URL
- `snapshot` - Screenshot pagina
- `click` - Click elemento
- `type` - Inserisci testo
- `evaluate` - Esegui JavaScript
- `wait_for` - Attendi elemento/testo

**Isolamento:**
- Container Docker per sessione (cleanup automatico)
- Tools filtrati per user preferences

---

### 6. Sistema Multi-Tenant (`backend/app/core/tenant_context.py`)

#### Architettura

**Tenant Model:**
- Tabella `tenants` con `id`, `name`, `schema_name`
- Default tenant creato automaticamente
- Supporto futuro per schema per tenant

**Isolamento Dati:**
- Tutte le tabelle hanno `tenant_id` (FK a `tenants`)
- Query sempre filtrate per `tenant_id`
- ChromaDB collections per tenant (`collection_tenant_{id}`)

**Tenant Resolution:**
1. Header `X-Tenant-ID` (futuro)
2. API Key (futuro)
3. Default tenant (backward compatibility)

**User Isolation:**
- Utenti collegati a tenant (`users.tenant_id`)
- Sessioni filtrate per `tenant_id` + `user_id`
- Integrazioni isolate per tenant + user

---

### 7. Observability (`backend/app/core/tracing.py`, `metrics.py`)

#### Tracing (OpenTelemetry)

**Trace Spans:**
- HTTP requests (automatico via middleware)
- Tool executions
- LLM calls
- Database operations

**Trace IDs:**
- Generati per ogni richiesta HTTP
- Inclusi in response headers (`X-Trace-ID`)
- Correlati frontend-backend

**Frontend Integration:**
- Frontend genera trace IDs
- Invia in header `X-Trace-ID`
- Backend correla con trace backend

#### Metrics (Prometheus)

**HTTP Metrics:**
- `http_requests_total` - Counter richieste
- `http_request_duration_seconds` - Histogram latenza
- `http_requests_errors_total` - Counter errori

**Tool Metrics:**
- `tool_executions_total` - Counter esecuzioni
- `tool_execution_duration_seconds` - Histogram durata
- `tool_executions_errors_total` - Counter errori

**LLM Metrics:**
- `llm_requests_total` - Counter richieste
- `llm_request_duration_seconds` - Histogram durata
- `llm_requests_errors_total` - Counter errori

**Endpoint:**
- `/metrics` - Prometheus scraping endpoint

---

### 8. Frontend Architecture (`frontend/`)

#### Struttura Next.js

```
frontend/
├── app/                    # Next.js App Router
│   ├── page.tsx           # Home (session list)
│   ├── sessions/[id]/     # Chat interface
│   ├── auth/              # Authentication pages
│   ├── admin/             # Admin panel
│   └── settings/          # User settings
├── components/             # React components
│   ├── ChatInterface.tsx  # Main chat UI
│   ├── MemoryView.tsx     # Memory visualization
│   ├── FileManager.tsx     # File upload/management
│   └── ...
├── contexts/               # React Context
│   └── AuthContext.tsx    # Authentication state
├── lib/                    # Utilities
│   ├── api.ts             # Axios client + interceptors
│   ├── tracing.ts         # Frontend tracing
│   └── errorHandler.ts    # Error handling
└── types/                  # TypeScript types
```

#### State Management

**Authentication:**
- JWT tokens in localStorage
- Refresh token automatico
- Protected routes con `ProtectedRoute` component

**API Communication:**
- Axios client con interceptors
- Auto-retry su errori di rete
- Trace ID correlation
- Error handling centralizzato

**Real-time Updates:**
- Server-Sent Events (SSE) per streaming chat
- WebSocket (futuro) per notifiche real-time

---

## 🔄 Flussi Principali

### 1. Chat Flow

```
User Input (Frontend)
│
├── POST /api/sessions/{id}/chat
│   ├── Authentication (JWT)
│   ├── Tenant Context Extraction
│   └── User Context Extraction
│
├── Context Assembly
│   ├── Retrieve session history
│   ├── Retrieve memory (short/medium/long-term)
│   ├── Load file content
│   ├── Get available tools
│   └── Build system prompt
│
├── LangGraph Execution
│   ├── Event Handler
│   ├── Orchestrator
│   ├── Tool Loop (iterativo)
│   │   ├── LLM decides tool
│   │   ├── Execute tool
│   │   └── Add result to context
│   ├── Knowledge Agent
│   ├── Integrity Agent
│   └── Response Formatter
│
├── Streaming Response (SSE)
│   └── Frontend updates UI in real-time
│
└── Background Tasks
    ├── Save messages to database
    ├── Extract memory (ConversationLearner)
    ├── Check contradictions (SemanticIntegrityChecker)
    └── Update session metadata
```

### 2. Memory Retrieval Flow

```
Query (from chat context)
│
├── Short-Term Memory
│   └── Check in-memory cache + database
│
├── Medium-Term Memory
│   ├── Query ChromaDB (semantic search)
│   └── Filter by session_id
│
├── Long-Term Memory
│   ├── Query ChromaDB (semantic search)
│   └── Filter by user_id (cross-session)
│
└── Combine Results
    ├── Deduplicate
    ├── Rank by relevance
    └── Inject into system prompt
```

### 3. Tool Execution Flow

```
LLM Tool Call Request
│
├── Tool Selection
│   ├── Base tools → Direct execution
│   ├── MCP tools → MCP Gateway
│   └── Integration tools → OAuth2 → External API
│
├── Execution
│   ├── Validate parameters
│   ├── Check permissions (tenant/user)
│   ├── Execute tool
│   └── Handle errors
│
├── Result Processing
│   ├── Format result
│   ├── Add to context
│   └── Index in memory (if relevant)
│
└── Return to LLM
    └── Continue tool loop if needed
```

---

## 🗄️ Database Schema

### Tabelle Principali

**Multi-Tenant:**
- `tenants` - Organizzazioni
- `users` - Utenti (collegati a tenant)

**Sessions & Messages:**
- `sessions` - Chat sessions (tenant_id, user_id)
- `messages` - Messaggi chat (session_id, role, content)

**Memory:**
- `memory_short` - Short-term memory (session_id, tenant_id)
- `memory_medium` - Medium-term memory (session_id, tenant_id)
- `memory_long` - Long-term memory (user_id, tenant_id)

**Integrations:**
- `integrations` - OAuth integrations (tenant_id, user_id, type, credentials)

**Files:**
- `files` - Uploaded files (user_id, tenant_id, session_id nullable, filepath, metadata)
  - Files are **user-scoped** (belong to user, not session)
  - Available across all user sessions
  - Can be deleted by user

**Notifications:**
- `notifications` - Notifiche utente (user_id, tenant_id, type, payload)

### ChromaDB Collections

**Per Tenant:**
- `file_embeddings_tenant_{id}` - File embeddings
- `session_memory_tenant_{id}` - Session memory embeddings
- `long_term_memory_tenant_{id}` - Long-term memory embeddings

---

## 🔐 Sicurezza

### Autenticazione

**JWT Tokens:**
- Access token (short-lived)
- Refresh token (long-lived)
- Token rotation automatica

**Password Security:**
- Bcrypt hashing
- Password reset con email verification

### Isolamento Dati

**Multi-Tenant:**
- Query sempre filtrate per `tenant_id`
- ChromaDB collections separate
- Verifica appartenenza risorse

**User-Level:**
- Sessioni filtrate per `user_id`
- Integrazioni isolate per utente
- Memory user-scoped
- Files user-scoped (available across all sessions)

### OAuth2 Integrations

**Token Storage:**
- Credenziali encrypted in database
- Token refresh automatico
- Scadenza gestita

---

## 📊 Performance & Scalability

### Ottimizzazioni

**Database:**
- Indici su `tenant_id`, `user_id`, `session_id`
- Query async con SQLAlchemy
- Connection pooling

**Memory:**
- In-memory cache per short-term memory
- ChromaDB collections cache
- Batch operations per embeddings

**LLM:**
- Streaming responses
- Context window optimization
- Tool calling efficiente

### Scalability Considerations

**Horizontal Scaling:**
- Stateless backend (JWT tokens)
- ChromaDB può essere distribuito
- PostgreSQL può essere replicato

**Bottlenecks Potenziali:**
- ChromaDB queries (mitigato con timeout)
- LLM calls (mitigato con streaming)
- File processing (background jobs)

---

## 🧪 Testing & Quality

### Test Coverage

**Unit Tests:**
- Evaluation framework (34 test unitari)
- Test cases (14 scenari)
- Integration tests (7 test)

**E2E Tests:**
- Web indexing (9/9 test passati)
- Email indexing (10/10 test passati)

### Code Quality

- Pydantic V2 compatible
- Type hints completi
- Error handling robusto
- Logging strutturato

---

## 🚀 Deployment

### Local Development

**Docker Compose:**
- PostgreSQL
- ChromaDB
- (Ollama esterno, llama.cpp nativo)

**Scripts:**
- `start.sh` - Avvia tutti i servizi
- `stop.sh` - Ferma tutti i servizi
- `restart_backend.sh` - Riavvia backend

### Production (Pianificato)

**Cloud Run:**
- Backend containerizzato
- Frontend build statico
- Database Cloud SQL
- ChromaDB su cloud

---

## 📈 Monitoring & Observability

### Tracing

- OpenTelemetry (con fallback semplice)
- Trace IDs correlati frontend-backend
- Spans per operazioni critiche

### Metrics

- Prometheus endpoint `/metrics`
- Dashboard frontend (`/admin/metrics`)
- Alerting (futuro)

### Logging

- Structured logging
- File + console output
- Trace ID nei log

---

## 🎯 Prossimi Sviluppi

### In Corso

- ✅ Observability (completato)
- ✅ Agent Evaluation System (completato)
- ⏳ Cloud Deployment (in attesa)

### Pianificato

- Gemini support (opzionale)
- Video dimostrativo
- Writeup finale per Kaggle

### Futuro

- WebSocket per notifiche real-time
- Proattività (monitoring eventi)
- WhatsApp Business API integration
- Memory provenance tracking
- Multi-dimensional memory retrieval

---

## 📚 Riferimenti

- **Documentazione**: `docs/` directory
- **Roadmap**: `docs/ROADMAP.md`
- **Kaggle Submission**: `docs/KAGGLE_SUBMISSION_ROADMAP.md`
- **Multi-Tenant**: `docs/MULTI_TENANT_IMPLEMENTATION.md`
- **Observability**: `docs/OBSERVABILITY.md`
- **Context Engineering**: `docs/CONTEXT_ENGINEERING_ANALYSIS.md`

---

**Ultimo aggiornamento**: 2025-11-17  
**Versione documento**: 1.0

