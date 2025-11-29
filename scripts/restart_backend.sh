#!/bin/bash
# Script per riavviare solo il backend (utile dopo aggiornamenti configurazione)

# Salva il path della root del progetto
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🔄 Riavvio Backend..."

# Termina processi esistenti sulla porta 8000
if lsof -ti:8000 > /dev/null 2>&1; then
    echo "⚠️  Trovati processi sulla porta 8000, terminazione..."
    lsof -ti:8000 | xargs kill -9 2>/dev/null
    sleep 2
else
    echo "ℹ️  Nessun processo trovato sulla porta 8000"
fi

# Verifica token MCP Gateway
echo ""
echo "🔍 Verifica configurazione MCP Gateway..."
cd "$PROJECT_ROOT/backend"
if [ -f ".env" ]; then
    if grep -q "MCP_GATEWAY_AUTH_TOKEN" .env; then
        TOKEN_PREVIEW=$(grep "MCP_GATEWAY_AUTH_TOKEN" .env | head -1 | cut -d'=' -f2 | cut -c1-30)
        echo "   Token trovato in .env: ${TOKEN_PREVIEW}..."
    else
        echo "   ⚠️  MCP_GATEWAY_AUTH_TOKEN non trovato in .env"
    fi
else
    echo "   ⚠️  File .env non trovato"
fi

# Set GOOGLE_APPLICATION_CREDENTIALS for Vertex AI if not already set
if [ -z "$GOOGLE_APPLICATION_CREDENTIALS" ] && [ -f "$PROJECT_ROOT/backend/credentials/knowledge-navigator-477022-95a2ce0ebf9a.json" ]; then
    export GOOGLE_APPLICATION_CREDENTIALS="$PROJECT_ROOT/backend/credentials/knowledge-navigator-477022-95a2ce0ebf9a.json"
    echo "✅ GOOGLE_APPLICATION_CREDENTIALS impostato automaticamente"
fi

# Attiva virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "❌ Virtual environment non trovato!"
    exit 1
fi

# Test che il token sia caricabile
echo ""
echo "🧪 Test caricamento configurazione..."
python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from app.core.config import settings
    token = settings.mcp_gateway_auth_token
    if token:
        print(f'   ✅ Token caricato: {token[:30]}...')
    else:
        print('   ⚠️  Token MCP Gateway non configurato')
except Exception as e:
    print(f'   ⚠️  Errore nel caricamento configurazione: {e}')
" 2>/dev/null || echo "   ⚠️  Impossibile verificare il token"

# Avvia il backend
echo ""
echo "🚀 Avvio backend..."
mkdir -p "$PROJECT_ROOT/logs"
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > "$PROJECT_ROOT/logs/backend.log" 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > /tmp/backend.pid
echo "   PID: $BACKEND_PID"

# Attendi che il backend sia pronto
echo ""
echo "⏳ Attesa avvio backend..."
BACKEND_READY=false
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        BACKEND_READY=true
        echo "✅ Backend pronto su http://localhost:8000"
        break
    fi
    sleep 1
done

if [ "$BACKEND_READY" = false ]; then
    echo "❌ Backend non risponde dopo 30 secondi"
    echo "   Controlla i log: tail -f logs/backend.log"
    exit 1
fi

echo ""
echo "📋 Informazioni:"
echo "   Log: tail -f logs/backend.log"
echo "   API Docs: http://localhost:8000/docs"
echo "   Health: http://localhost:8000/health"

