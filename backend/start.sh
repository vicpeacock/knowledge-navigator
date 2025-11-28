#!/bin/bash

# Set GOOGLE_APPLICATION_CREDENTIALS for Vertex AI if not already set
if [ -z "$GOOGLE_APPLICATION_CREDENTIALS" ] && [ -f "$(dirname "$0")/credentials/knowledge-navigator-477022-95a2ce0ebf9a.json" ]; then
    export GOOGLE_APPLICATION_CREDENTIALS="$(cd "$(dirname "$0")" && pwd)/credentials/knowledge-navigator-477022-95a2ce0ebf9a.json"
    echo "✅ GOOGLE_APPLICATION_CREDENTIALS impostato automaticamente"
fi

# Script per avviare il backend, terminando eventuali processi esistenti

cd "$(dirname "$0")"

# Termina processi esistenti sulla porta 8000
echo "🔍 Verificando processi sulla porta 8000..."
if lsof -ti:8000 > /dev/null 2>&1; then
    echo "⚠️  Trovati processi sulla porta 8000, terminazione..."
    lsof -ti:8000 | xargs kill -9 2>/dev/null
    sleep 2
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

# Avvia il backend
echo "🚀 Avviando backend..."
mkdir -p logs
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > logs/backend.log 2>&1 &

# Attendi l'avvio
sleep 3

# Verifica che sia partito
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend avviato correttamente su http://localhost:8000"
    echo "📋 Log: tail -f logs/backend.log"
else
    echo "❌ Backend non risponde. Controlla i log: tail -f logs/backend.log"
    exit 1
fi

