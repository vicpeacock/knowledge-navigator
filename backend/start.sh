#!/bin/bash
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
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > backend.log 2>&1 &

# Attendi l'avvio
sleep 3

# Verifica che sia partito
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend avviato correttamente su http://localhost:8000"
    echo "📋 Log: tail -f backend.log"
else
    echo "❌ Backend non risponde. Controlla i log: tail -f backend.log"
    exit 1
fi

