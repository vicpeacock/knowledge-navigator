# Knowledge Navigator - Quick Start Guide

## Prerequisites

1. **Docker & Docker Compose** - For PostgreSQL and ChromaDB
2. **Python 3.11+** - For backend
3. **Node.js 18+** - For frontend
4. **Ollama** - Running on port 11434 with a model (e.g., `llama3`)

## Setup Steps

### 1. Start Databases

```bash
docker-compose up -d
```

This will start:
- PostgreSQL on port 5432
- ChromaDB on port 8001 (changed from 8000 to avoid conflict with backend)

### 2. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r ../requirements.txt
```

### 3. Initialize Database

```bash
cd backend
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

Or use the init script:
```bash
python app/db/init_db.py
```

### 4. Frontend Setup

```bash
cd frontend
npm install
```

### 5. Environment Configuration

Create a `.env` file in the root directory (or copy from `.env.example` if available):

```env
DATABASE_URL=postgresql+asyncpg://knavigator:knavigator_pass@localhost:5432/knowledge_navigator
CHROMADB_HOST=localhost
CHROMADB_PORT=8001
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
MCP_GATEWAY_URL=http://localhost:3002
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 6. Start Services

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
# Il frontend sarà disponibile su http://localhost:3003 (3000/3001 occupate)
```

### 7. Access Application

- Frontend: http://localhost:3003 (3000 occupata da OpenWebUI, 3001 occupata)
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Usage

1. **Create a Session**: Click "New Session" on the dashboard
2. **Chat**: Type messages and get AI responses
3. **Upload Files**: Click "Upload File" to analyze documents
4. **Memory**: The system automatically uses short/medium/long-term memory
   - Access memory management via menu or `/memory` page
   - Note: "Integrations" and "Memory" buttons removed from SessionList (available in main menu only)
5. **Tools**: Access MCP tools via API endpoints
6. **Profile Settings**: Configure timezone and user preferences at `/settings/profile`
7. **Notifications**: Click bell icon 🔔 for real-time notifications (SSE enabled)

## Testing

Test the API:
```bash
# List sessions
curl http://localhost:8000/api/sessions

# Create session
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Session"}'

# Chat
curl -X POST http://localhost:8000/api/sessions/{session_id}/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "session_id": "{session_id}", "use_memory": true}'
```

## Troubleshooting

- **Database connection errors**: Ensure PostgreSQL is running (`docker-compose ps`)
- **Ollama errors**: Ensure Ollama is running and model is downloaded (`ollama list`)
- **ChromaDB errors**: Check ChromaDB health (`curl http://localhost:8001/api/v1/heartbeat`)
- **Port conflicts**: Change ports in docker-compose.yml and .env

