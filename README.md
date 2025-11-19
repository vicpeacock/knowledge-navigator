# Knowledge Navigator

Personal AI Assistant - Sistema multi-agente per gestione conoscenza e automazione.

## 🚀 Quick Start

```bash
# Avvia tutti i servizi
./scripts/start.sh

# Ferma tutti i servizi
./scripts/stop.sh

# Riavvia solo il backend
./scripts/restart_backend.sh
```

## 📁 Struttura Progetto

- **`backend/`** - Backend FastAPI con agenti LangGraph
- **`frontend/`** - Frontend Next.js/React
- **`scripts/`** - Script di servizio (start, stop, restart, etc.)
- **`docs/`** - Documentazione del progetto
- **`tools/`** - Strumenti di sviluppo e infrastruttura

## ✨ Funzionalità Principali

### 🤖 Sistema Multi-Agente
- Architettura LangGraph per orchestrazione agenti
- Tool calling dinamico (LLM decide quando usare tool)
- Memoria multi-livello (short/medium/long-term)
- RAG con ChromaDB per ricerca semantica

### 📅 Sessioni Giornaliere
- Una sessione per giorno per utente
- Archiviazione automatica con riassunto
- Transizione di giorno con dialog di conferma
- Supporto timezone personalizzato (configurabile nel Profile)

### 📧 Integrazioni
- **Gmail**: Lettura email, invio, archiviazione, risposte automatiche
- **Google Calendar**: Lettura eventi, query in linguaggio naturale
- **Navigazione Web**: Browser Playwright, ricerca web Ollama

### 🔔 Sistema Notifiche Avanzato
- Notifiche real-time con Server-Sent Events (SSE)
- Pagina dedicata `/notifications` con filtri e paginazione
- Raggruppamento per tipo
- Cancellazione batch
- Ottimizzazioni database per performance
- UI semplificata con bottoni testo + icona
- Popup allargato (500px) per migliore usabilità

### 💾 Gestione Memoria
- Memoria a lungo termine con gestione dedicata
- Cancellazione batch con checkboxes
- Ricerca semantica avanzata
- Consolidamento automatico duplicati

### 👥 Multi-Tenancy & Multi-User
- Isolamento dati completo per tenant
- Isolamento dati per utente
- Autenticazione JWT con refresh tokens
- Ruoli utente (admin, user, viewer)
- Gestione profilo utente con configurazione timezone

## 📚 Documentazione

Tutta la documentazione è in `docs/`:
- **`docs/ROADMAP.md`** - Roadmap generale del progetto
- **`docs/DAILY_SESSIONS_AND_NOTIFICATIONS.md`** - Sistema sessioni giornaliere e miglioramenti notifiche
- **`docs/LANGGRAPH_REFACTORING.md`** - Refactoring completo LangGraph con test e fallback multipli
- **`docs/SCRIPTS.md`** - Documentazione degli script
- **`docs/KAGGLE_SUBMISSION_ROADMAP.md`** - Roadmap challenge Kaggle
- **`docs/PROACTIVITY_ARCHITECTURE.md`** - Architettura sistema proattività
- E altri...

## 🛠️ Script Disponibili

Tutti gli script sono in `scripts/`:
- `start.sh` - Avvia tutti i servizi
- `stop.sh` - Ferma tutti i servizi
- `restart_backend.sh` - Riavvia solo il backend
- `cleanup_sessions_and_memory.py` - Pulisce sessioni e memoria
- `create_today_session.py` - Crea sessione giornaliera
- Altri script di utilità...

Vedi `docs/SCRIPTS.md` per la documentazione completa.

## 🧪 Testing

```bash
# Backend tests
cd backend && source venv/bin/activate && python -m pytest

# Frontend tests
cd frontend && npm test
```

## 📊 Statistiche

- **Test Coverage**: 31/31 test passati (100%)
- **Fase 1 Completamento**: ~95%
- **Fase 2 Completamento**: ~90%
- **Code Quality**: Nessun warning, Pydantic V2 compatibile

## 🌐 Deployment

### Locale (Development)
- **LLM**: Ollama + llama.cpp con supporto Metal GPU
- **Configurazione**: Usa `LLM_PROVIDER=ollama` in `.env`
- **Switch**: `./scripts/switch-env.sh local`

### Cloud (Production)
- **LLM**: Gemini API (Google AI Studio) - Nessuna GPU necessaria
- **Configurazione**: Usa `LLM_PROVIDER=gemini` in `.env`
- **Switch**: `./scripts/switch-env.sh cloud`
- **Deployment**: Google Cloud Run con Docker
- **Bonus**: +5 punti Kaggle challenge per uso Gemini

**Note**: I due deployment non interferiscono tra loro. Usa gli script `switch-env.sh` e `check-env.sh` per gestire gli ambienti.

Vedi `cloud-run/README.md` per dettagli sul deployment cloud.

## 🔧 Tecnologie

- **Backend**: FastAPI, LangGraph, SQLAlchemy, ChromaDB
- **LLM**: Ollama/llama.cpp (locale) o Gemini API (cloud)
- **Frontend**: Next.js 14, React, TypeScript, TailwindCSS
- **Database**: PostgreSQL, ChromaDB
- **Observability**: OpenTelemetry, Prometheus

## 📝 Note

Per maggiori dettagli sulle funzionalità recenti, consulta:
- `docs/DAILY_SESSIONS_AND_NOTIFICATIONS.md` - Sessioni giornaliere e notifiche
- `docs/ROADMAP.md` - Roadmap completa del progetto
