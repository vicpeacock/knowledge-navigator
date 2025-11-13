#!/bin/bash
# Script wrapper per pulire contraddizioni e notifiche
# Assicura che venga usato l'ambiente virtuale corretto

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$BACKEND_DIR" || exit 1

# Attiva l'ambiente virtuale se esiste
if [ -f "venv/bin/activate" ]; then
    echo "Attivando venv..."
    source venv/bin/activate
elif [ -f ".venv/bin/activate" ]; then
    echo "Attivando .venv..."
    source .venv/bin/activate
else
    echo "⚠️  Nessun ambiente virtuale trovato. Assicurati di essere nell'ambiente virtuale corretto."
    echo "   Provo comunque ad eseguire lo script..."
fi

# Esegui lo script Python
python scripts/clean_contradictions.py

