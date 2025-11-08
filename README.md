# Knowledge Navigator

Un assistente AI personale che integra calendario, email, memoria multi-livello e capacità di navigazione web.

## Caratteristiche

- 🤖 **Assistente AI Conversazionale**: Interfaccia chat basata su Ollama (gpt-oss:20b)
- 📅 **Integrazione Calendario**: Lettura eventi da Google Calendar con query in linguaggio naturale
- 📧 **Integrazione Email**: Lettura e riassunto email da Gmail
- 🌐 **Navigazione Web**: 
  - Ricerca web nativa Ollama (web_search, web_fetch)
  - Tool browser Playwright per navigazione avanzata
  - Toggle "Web Search" per forzare ricerca web (come Ollama desktop)
  - Indicizzazione automatica contenuti web in memoria long-term
- 💾 **Memoria Multi-livello**:
  - **Short-term**: Contesto della sessione corrente
  - **Medium-term**: Memoria persistente per sessione (30 giorni)
  - **Long-term**: Memoria condivisa tra tutte le sessioni con indicizzazione automatica
- 📁 **Gestione File**: Upload e indicizzazione file (PDF, DOCX, XLSX, TXT) con RAG
- 🔧 **Tool Calling**: Sistema dinamico dove l'LLM decide autonomamente quando usare tool esterni
- ✅ **Test Suite Completa**: Test automatizzati per indicizzazione web ed email

## Stack Tecnologico

### Backend
- **FastAPI**: Framework Python per l'API REST
- **PostgreSQL**: Database relazionale per metadata
- **ChromaDB**: Vector database per embeddings e ricerca semantica
- **Ollama**: LLM locale (gpt-oss:20b)
- **SQLAlchemy**: ORM asincrono

### Frontend
- **Next.js 14**: Framework React con App Router
- **TypeScript**: Tipizzazione statica
- **Tailwind CSS**: Styling
- **react-markdown**: Rendering markdown nelle risposte

## Struttura della Repository

```
docs/
  backend/           Documentazione tecnica specifica del backend (architetture, design notes)
  *.md               Guide operative e reference per setup, integrazioni e troubleshooting
tests/
  backend/unit/      Test automatici del backend (pytest)
  backend/langgraph/ Test del grafo conversazionale e dei nuovi planner
  backend/manual/    Script di verifica manuale / debug (marcati come skipped)
tools/
  backend/           Utility Python per manutenzione (check DB, restore, setup env)
  infra/             Script shell per avvio/stop servizi e auto-versioning
others/
  logs/              Output log consolidati
  uploads/           File caricati durante i test o l'utilizzo locale
backend/, frontend/  Codice applicativo invariato
```

## Setup

### Prerequisiti

- Python 3.13+
- Node.js 18+
- PostgreSQL 14+
- Ollama con modello `gpt-oss:20b`
- ChromaDB (via Docker o locale)

### Installazione Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Su Windows: venv\Scripts\activate
pip install -r requirements.txt

# Copia .env.example e configura
cp .env.example .env
# Modifica .env con le tue configurazioni
```

### Installazione Frontend

```bash
cd frontend
npm install

# Copia .env.example se necessario
# NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Database Setup

```bash
# Avvia PostgreSQL e ChromaDB (es. via Docker Compose)
docker-compose up -d

# Esegui migrazioni
cd backend
alembic upgrade head
```

### Avvio

```bash
# Terminal 1: Backend
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev
```

L'applicazione sarà disponibile su `http://localhost:3003`

## Configurazione Google OAuth

Per utilizzare le integrazioni Google Calendar e Gmail:

1. Crea un progetto su [Google Cloud Console](https://console.cloud.google.com/)
2. Abilita Google Calendar API e Gmail API
3. Crea credenziali OAuth 2.0 (Web application)
4. Aggiungi gli authorized redirect URIs:
   - `http://localhost:8000/api/integrations/calendars/oauth/callback`
   - `http://localhost:8000/api/integrations/emails/oauth/callback`
5. Copia `Client ID` e `Client Secret` nel file `.env`

Vedi `SETUP_GOOGLE_CALENDAR.md` per istruzioni dettagliate.

## Licenza

Proprietario - Uso Privato

## Autore

Knowledge Navigator Development Team