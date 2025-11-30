# Knowledge Navigator - Architettura Interna Completa

## Panoramica

Knowledge Navigator è un sistema multi-agente AI enterprise-grade costruito con FastAPI, Next.js, e LangGraph. Questo documento fornisce una panoramica completa dell'architettura del sistema.

**Versione**: 0.1.0
**Ultimo Aggiornamento**: 2025-01-XX

---

## Indice Documentazione Interna

1. **[INTERNAL_MEMORY_SYSTEM.md](INTERNAL_MEMORY_SYSTEM.md)** - Sistema memoria multi-livello dettagliato
2. **[INTERNAL_MULTI_AGENT_SYSTEM.md](INTERNAL_MULTI_AGENT_SYSTEM.md)** - Architettura multi-agente e LangGraph
3. **[INTERNAL_TOOL_SYSTEM.md](INTERNAL_TOOL_SYSTEM.md)** - Sistema tool e integrazioni
4. **[INTERNAL_RAG_IMPLEMENTATION.md](INTERNAL_RAG_IMPLEMENTATION.md)** - Implementazione RAG e embeddings
5. **[INTERNAL_OBSERVABILITY.md](INTERNAL_OBSERVABILITY.md)** - Sistema observability (tracing, metrics)
6. **[INTERNAL_DEPLOYMENT_ARCHITECTURE.md](INTERNAL_DEPLOYMENT_ARCHITECTURE.md)** - Architettura deployment (Cloud Run, Docker, ecc.)

---

## Stack Tecnologico

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 16 (dati strutturati) + ChromaDB (vector database per RAG)
- **LLM Providers**: Vertex AI (Gemini 2.5 Flash), Ollama locale, Gemini API REST
- **Agent Framework**: LangGraph per orchestrazione multi-agente
- **Observability**: OpenTelemetry (tracing) + Prometheus (metrics)
- **Autenticazione**: JWT con refresh tokens

### Frontend
- **Framework**: Next.js 14+ (React)
- **Styling**: Tailwind CSS
- **State Management**: React Context API
- **HTTP Client**: Axios con interceptors per tracing

### Infrastruttura
- **Container**: Docker Compose (PostgreSQL, ChromaDB)
- **Deployment**: Google Cloud Run
- **Storage**: Google Cloud Storage per file
- **Process Management**: Script bash per gestione servizi
- **Background Jobs**: Task queue asincrona

---

## Componenti Principali

### 1. Backend FastAPI

Il backend è organizzato in moduli:
- `/api/` - Endpoint REST API
- `/core/` - Componenti core (memory manager, clients, config)
- `/agents/` - Sistema multi-agente LangGraph
- `/services/` - Servizi business logic
- `/models/` - Modelli database SQLAlchemy

### 2. Sistema Multi-Agente (LangGraph)

Orchestrazione tramite LangGraph con agenti specializzati:
- **Main Agent**: Gestisce interazioni utente e tool calling
- **Knowledge Agent**: Recupera informazioni da memoria
- **Integrity Agent**: Verifica contraddizioni (background)
- **Planner Agent**: Crea piani multi-step
- **Notification Collector**: Aggrega notifiche

### 3. Memoria Multi-Livello

Sistema a tre livelli:
- **Short-term** (1 ora TTL): Context immediato sessione
- **Medium-term** (30 giorni TTL): Informazioni rilevanti sessione
- **Long-term** (persistente): Conoscenza cross-sessione con ricerca semantica

### 4. Tool System

Integrazioni esterne:
- **Google Workspace**: Calendar, Gmail, Drive, Tasks
- **MCP Tools**: Browser automation, tool dinamici
- **Web Search**: Google Custom Search API
- **File Management**: Upload, analisi, gestione

---

## Flusso di Esecuzione

1. **User Input** → Chat endpoint riceve richiesta
2. **Context Assembly**: Sistema assembla context (history, memory, files, tools)
3. **LangGraph Execution**: State machine esegue agenti in sequenza
4. **Tool Execution**: Tool chiamati iterativamente fino a completamento
5. **Response Generation**: LLM genera risposta con context
6. **Background Processing**: Memory extraction, integrity checks

---

## Decisioni Progettuali

### Perché LangGraph?
- Orchestrazione complessa multi-agente richiede state machine robusta
- Integrazione nativa con LLM e tool calling
- Facilita debugging e observability del flusso

### Perché Memoria Multi-Livello?
- Short-term per context immediato
- Medium-term per informazioni sessione
- Long-term per conoscenza persistente cross-sessione
- Bilanciamento tra performance e persistenza

### Perché ChromaDB?
- Vector database leggero e performante
- Supporto multi-tenant nativo
- Integrazione semplice con Python ecosystem
- Supporto cloud e locale

---

## Limitazioni Note

1. **Context Window**: Limitato dalla capacità LLM (128k token per Gemini 2.5)
2. **Memory Retrieval**: Top-K semantic search, non garantisce completezza
3. **Tool Execution**: Sequenziale per garantire coerenza
4. **Background Tasks**: Eseguono asincrono ma non bloccano risposte

---

## Riferimenti

Per dettagli implementativi, consulta i documenti specializzati elencati nell'indice sopra.
