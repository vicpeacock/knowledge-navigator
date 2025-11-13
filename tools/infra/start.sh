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
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo $BACKEND_PID > /tmp/backend.pid
cd ..

# Avvio Frontend
echo "🎨 Avvio frontend..."
cd "$PROJECT_ROOT/frontend"
npm run dev &
FRONTEND_PID=$!
echo $FRONTEND_PID > /tmp/frontend.pid
cd ..

sleep 5

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
echo "🛑 Per fermare: ./stop.sh"

