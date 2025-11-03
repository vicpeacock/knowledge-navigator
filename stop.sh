#!/bin/bash

echo "🛑 Arresto Knowledge Navigator..."

if [ -f /tmp/backend.pid ]; then
    kill $(cat /tmp/backend.pid) 2>/dev/null && echo "✓ Backend fermato"
    rm /tmp/backend.pid
fi

if [ -f /tmp/frontend.pid ]; then
    kill $(cat /tmp/frontend.pid) 2>/dev/null && echo "✓ Frontend fermato"
    rm /tmp/frontend.pid
fi

echo "✅ Servizi arrestati"

