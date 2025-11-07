#!/bin/bash
# Script per avviare llama-server con Phi-3-mini per Background Agent

MODEL_PATH="$HOME/models/llama-cpp/Phi-3-mini-4k-instruct-q4.gguf"
PORT=11435
LOG_FILE="/tmp/llama-background.log"

# Verificare che il modello esista
if [ ! -f "$MODEL_PATH" ]; then
    echo "❌ Modello non trovato: $MODEL_PATH"
    exit 1
fi

# Fermare eventuali istanze esistenti sulla porta
lsof -ti:$PORT | xargs kill -9 2>/dev/null
sleep 2

# Avviare llama-server
echo "🚀 Avviando llama-server con Phi-3-mini su porta $PORT..."
cd "$(dirname "$MODEL_PATH")"

llama-server \
  -m "$(basename "$MODEL_PATH")" \
  --port $PORT \
  --host 127.0.0.1 \
  --ctx-size 4096 \
  --threads 8 \
  --n-gpu-layers 999 \
  --keep-alive 5m \
  > "$LOG_FILE" 2>&1 &

PID=$!
echo "✅ llama-server avviato (PID: $PID)"
echo "📝 Log: $LOG_FILE"
echo "🌐 API: http://localhost:$PORT/v1/chat/completions"
echo ""
echo "Per fermare: kill $PID"

