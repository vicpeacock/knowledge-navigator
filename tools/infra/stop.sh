#!/bin/bash

echo "🛑 Arresto Knowledge Navigator..."

# Ferma backend
if [ -f /tmp/backend.pid ]; then
    kill $(cat /tmp/backend.pid) 2>/dev/null && echo "✓ Backend fermato"
    rm /tmp/backend.pid
fi

# Ferma frontend
if [ -f /tmp/frontend.pid ]; then
    kill $(cat /tmp/frontend.pid) 2>/dev/null && echo "✓ Frontend fermato"
    rm /tmp/frontend.pid
fi

# Ferma llama.cpp (porta 11435)
if [ -f /tmp/llama_background.pid ]; then
    kill $(cat /tmp/llama_background.pid) 2>/dev/null && echo "✓ llama.cpp fermato"
    rm /tmp/llama_background.pid
fi

# Libera le porte (kill forzato di eventuali processi rimasti)
echo "🔓 Liberazione porte..."
for port in 8000 3003 11435; do
    lsof -ti:$port | xargs kill -9 2>/dev/null && echo "✓ Porta $port liberata" || true
done

# Ferma eventuali processi llama-server rimasti
pkill -9 -f "llama-server.*11435" 2>/dev/null && echo "✓ Processi llama-server terminati" || true

sleep 1

echo "✅ Servizi arrestati e porte liberate"

