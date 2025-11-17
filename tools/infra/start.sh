#!/bin/bash

# Script per avviare Knowledge Navigator

# Salva il path della root del progetto
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "🚀 Avvio Knowledge Navigator..."

# Verifica Docker
cd "$PROJECT_ROOT"
if ! docker-compose ps | grep -q "Up"; then
    echo "📦 Avvio database..."
    docker-compose up -d
    sleep 5
fi

# Verifica e avvia Ollama (se necessario)
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "⚠️  Ollama non risponde su porta 11434"
    echo "   Assicurati che Ollama sia in esecuzione: ollama serve"
else
    echo "✓ Ollama attivo"
fi

# Verifica e avvia llama.cpp (porta 11435)
if ! curl -s http://localhost:11435/v1/models > /dev/null 2>&1; then
    echo "🤖 Avvio llama.cpp..."
    MODEL_PATH="$HOME/models/llama-cpp/Phi-3-mini-4k-instruct-q4.gguf"
    
    if [ ! -f "$MODEL_PATH" ]; then
        echo "⚠️  Modello llama.cpp non trovato: $MODEL_PATH"
        echo "   Salto avvio llama.cpp (il backend userà Ollama per background)"
    else
        # Ferma eventuali istanze esistenti
        lsof -ti:11435 | xargs kill -9 2>/dev/null
        sleep 1
        
        # Avvia llama-server
        cd "$(dirname "$MODEL_PATH")"
        nohup llama-server \
          -m "$(basename "$MODEL_PATH")" \
          --port 11435 \
          --host 127.0.0.1 \
          --ctx-size 4096 \
          --threads 8 \
          --n-gpu-layers 999 \
          > /tmp/llama-background.log 2>&1 &
        LLAMA_PID=$!
        echo $LLAMA_PID > /tmp/llama_background.pid
        disown $LLAMA_PID
        echo "✓ llama.cpp avviato (PID: $LLAMA_PID)"
        sleep 2
    fi
else
    echo "✓ llama.cpp già attivo"
fi

# Avvio Backend
echo "⚙️  Avvio backend..."
cd "$PROJECT_ROOT/backend"

# Termina processi esistenti sulla porta 8000
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
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > "$PROJECT_ROOT/backend/backend.log" 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > /tmp/backend.pid
cd ..

# Attendi che il backend sia pronto
echo "⏳ Attesa avvio backend..."
BACKEND_READY=false
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        BACKEND_READY=true
        echo "✅ Backend pronto"
        break
    fi
    sleep 1
done

if [ "$BACKEND_READY" = false ]; then
    echo "❌ Backend non risponde dopo 30 secondi. Controlla i log: tail -f backend/backend.log"
    exit 1
fi

# Avvio Frontend
echo "🎨 Avvio frontend..."

# Termina processi esistenti sulla porta 3003
if lsof -ti:3003 > /dev/null 2>&1; then
    echo "⚠️  Trovati processi sulla porta 3003, terminazione..."
    lsof -ti:3003 | xargs kill -9 2>/dev/null
    sleep 2
fi

cd "$PROJECT_ROOT/frontend"

# Verifica che node_modules esista
if [ ! -d "node_modules" ]; then
    echo "📦 Installazione dipendenze frontend..."
    npm install
fi

# Avvia il frontend
npm run dev > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > /tmp/frontend.pid
cd ..

# Attendi che il frontend sia pronto
echo "⏳ Attesa avvio frontend..."
FRONTEND_READY=false
for i in {1..60}; do
    if curl -s http://localhost:3003 > /dev/null 2>&1; then
        # Verifica che i chunk siano accessibili
        if curl -s http://localhost:3003/_next/static/chunks/webpack.js > /dev/null 2>&1; then
            FRONTEND_READY=true
            echo "✅ Frontend pronto"
            break
        fi
    fi
    sleep 1
done

if [ "$FRONTEND_READY" = false ]; then
    echo "⚠️  Frontend non completamente pronto dopo 60 secondi. Controlla i log: tail -f /tmp/frontend.log"
    echo "   Il frontend potrebbe essere ancora in avvio..."
fi

echo ""
echo "✅ Servizi avviati!"
echo ""
echo "📊 Status:"
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:3003"
echo "  API Docs: http://localhost:8000/docs"
if [ -f /tmp/llama_background.pid ]; then
    echo "  llama.cpp: http://localhost:11435/v1"
fi
echo ""
echo "📋 Log:"
echo "  Backend:  tail -f backend/backend.log"
echo "  Frontend: tail -f /tmp/frontend.log"
echo ""
echo "🛑 Per fermare: ./stop.sh"

