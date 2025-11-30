# Knowledge Navigator

**Multi-Agent AI Assistant for Enterprise Knowledge Management**

Knowledge Navigator is a production-ready, enterprise-grade multi-agent AI assistant built with LangGraph, FastAPI, and Next.js. It combines advanced memory systems, comprehensive tool integration, and full observability to help knowledge workers manage information and automate workflows.

**🏆 Kaggle Submission**: Enterprise Agents Track  
**🌐 Live Demo**: [Backend](https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app) | [Frontend](https://knowledge-navigator-frontend-osbdwu5a7q-uc.a.run.app)  
**📚 Documentation**: See [KAGGLE_SUBMISSION_WRITEUP.md](./KAGGLE_SUBMISSION_WRITEUP.md) for complete submission details

## 🎯 Problem Statement

Knowledge workers face information overload, context loss, and manual repetitive tasks across multiple platforms. Knowledge Navigator solves these challenges by providing an intelligent, multi-agent AI assistant that:

- **Maintains Context**: Three-tier memory system (short/medium/long-term) with semantic search
- **Automates Tasks**: Email triage, calendar management, information retrieval
- **Integrates Tools**: Google Workspace (Calendar, Gmail, Tasks), MCP, web search
- **Provides Observability**: Full tracing and metrics for production monitoring

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- PostgreSQL 16+ (or use Supabase)
- ChromaDB (or use ChromaDB Cloud)

### Local Development

```bash
# Clone repository
git clone https://github.com/vicpeacock/knowledge-navigator.git
cd knowledge-navigator

# Setup backend
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Setup frontend
cd ../frontend
npm install

# Configure environment
cp .env.example .env
# Edit .env with your configuration

# Start services
cd ..
./scripts/start.sh

# Access application
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Cloud Deployment (Google Cloud Run)

See [cloud-run/DEPLOYMENT_WITHOUT_MCP.md](./cloud-run/DEPLOYMENT_WITHOUT_MCP.md) for detailed deployment instructions.

**Quick Deploy**:
```bash
cd cloud-run
./deploy-enhanced.sh
```

## 📁 Struttura Progetto

- **`backend/`** - Backend FastAPI con agenti LangGraph
- **`frontend/`** - Frontend Next.js/React
- **`scripts/`** - Script di servizio (start, stop, restart, etc.)
- **`docs/`** - Documentazione del progetto
- **`tools/`** - Strumenti di sviluppo e infrastruttura

## ✨ Key Features

### 🤖 Multi-Agent System (LangGraph)
- **Specialized Agents**: Main, Knowledge, Integrity, Planner, Notification Collector
- **Dynamic Tool Calling**: LLM decides which tools to use based on context
- **State Machine**: Sophisticated orchestration with LangGraph
- **Background Processing**: Asynchronous tasks (memory extraction, integrity checks)

### 💾 Advanced Memory System
- **Three-Tier Architecture**:
  - **Short-Term** (1 hour TTL): Session-specific context
  - **Medium-Term** (30 days TTL): Session-relevant information
  - **Long-Term** (Persistent): Cross-session knowledge
- **Semantic Search**: ChromaDB for efficient similarity search
- **Contradiction Detection**: Advanced integrity checking with confidence thresholding
- **Memory Consolidation**: Automatic deduplication and merging

### 🛠️ Comprehensive Tool Integration
- **MCP Tools**: Browser automation (Playwright), dynamic tools from MCP servers
- **Google Workspace**: Calendar (read events, natural language queries), Gmail (read, send, archive), Tasks (create, list, update)
- **Built-in Tools**: Web search (Google Custom Search API), file upload/analysis
- **Custom Tools**: User-defined tools via MCP Gateway
- **File Management**: User-scoped file storage (files persist across sessions, can be deleted)

### 📊 Full Observability
- **Tracing**: OpenTelemetry with distributed tracing across frontend and backend
- **Metrics**: Prometheus metrics (performance, errors, agent behavior, memory operations)
- **Dashboard**: Real-time metrics dashboard at `/admin/metrics`

### 👥 Enterprise Features
- **Multi-Tenancy**: Complete data isolation per tenant
- **User Isolation**: User-specific data within tenants
- **Authentication**: JWT with refresh tokens
- **Authorization**: Role-based access control (admin, user, viewer)
- **Security**: Encrypted credentials for OAuth integrations

### 🔔 Proactive Notifications
- **Real-time Updates**: Server-Sent Events (SSE) for live notifications
- **Background Monitoring**: Email and calendar event monitoring
- **Intelligent Filtering**: User-specific notification preferences

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

### Production Deployment (Google Cloud Run)

**Live URLs**:
- **Backend**: https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app
- **Frontend**: https://knowledge-navigator-frontend-osbdwu5a7q-uc.a.run.app
- **API Docs**: https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app/docs

**Configuration**:
- **LLM**: Vertex AI (Gemini 2.5 Flash)
- **Database**: Supabase (PostgreSQL)
- **Vector DB**: ChromaDB Cloud
- **Auto-scaling**: Enabled

See [cloud-run/DEPLOYMENT_WITHOUT_MCP.md](./cloud-run/DEPLOYMENT_WITHOUT_MCP.md) for detailed deployment instructions.

### Local Development

- **LLM**: Ollama + llama.cpp (with Metal GPU support on macOS)
- **Configuration**: Use `LLM_PROVIDER=ollama` in `.env`
- **Switch**: `./scripts/switch-env.sh local`

## 🏗️ Architecture

Knowledge Navigator uses a sophisticated multi-agent architecture:

1. **LangGraph State Machine**: Orchestrates specialized agents
2. **Multi-Level Memory**: Short/medium/long-term with semantic search
3. **Tool System**: MCP, Google Workspace, custom tools
4. **Observability**: Full tracing and metrics
5. **Multi-Tenancy**: Complete data isolation

See [docs/ARCHITECTURE_ANALYSIS.md](./docs/ARCHITECTURE_ANALYSIS.md) for detailed architecture documentation.

## 🔧 Technology Stack

- **Backend**: FastAPI, LangGraph, SQLAlchemy, ChromaDB
- **LLM**: Vertex AI (Gemini 2.5 Flash) / Ollama (local development)
- **Frontend**: Next.js 14, React, TypeScript, TailwindCSS
- **Database**: PostgreSQL (Supabase), ChromaDB Cloud
- **Observability**: OpenTelemetry (tracing), Prometheus (metrics)
- **Deployment**: Google Cloud Run (Docker)

## 📚 Documentation

- **[KAGGLE_SUBMISSION_WRITEUP.md](./KAGGLE_SUBMISSION_WRITEUP.md)** - Complete Kaggle submission writeup
- **[docs/ARCHITECTURE_ANALYSIS.md](./docs/ARCHITECTURE_ANALYSIS.md)** - Detailed architecture analysis
- **[docs/ROADMAP.md](./docs/ROADMAP.md)** - Project roadmap
- **[cloud-run/DEPLOYMENT_WITHOUT_MCP.md](./cloud-run/DEPLOYMENT_WITHOUT_MCP.md)** - Cloud deployment guide

## 🏆 Kaggle Challenge

**Track**: Enterprise Agents  
**Status**: ✅ Ready for submission

**Requirements Met** (5/7):
- ✅ Multi-agent system (LangGraph)
- ✅ Tools (MCP, Google Workspace, custom)
- ✅ Sessions & Memory (three-tier memory)
- ✅ Observability (tracing + metrics)
- ✅ Agent Deployment (Cloud Run)

**Bonus Points**:
- ✅ Gemini Integration (Vertex AI)
- ✅ Cloud Deployment (Google Cloud Run)
- ⏳ YouTube Video (to be created)

## 📝 License

This project is part of the Kaggle Agents Intensive Capstone Project.

## 🤝 Contributing

This is a capstone project submission. For questions or feedback, please open an issue on GitHub.
