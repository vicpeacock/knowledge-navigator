#!/bin/bash
# Script per eseguire le migrations manualmente sul database Supabase

set -e

echo "🔄 Eseguendo migrations manualmente sul database Supabase..."

# Carica variabili ambiente
if [ -f .env.cloud-run ]; then
    set -a
    source .env.cloud-run
    set +a
fi

# Verifica che DATABASE_URL sia impostato
if [ -z "$DATABASE_URL" ]; then
    echo "❌ ERRORE: DATABASE_URL non è impostato"
    exit 1
fi

echo "📦 Database URL: ${DATABASE_URL:0:50}..."

# Esegui migrations usando Docker
cd backend

echo "🔄 Eseguendo: alembic upgrade head"
docker run --rm \
    -v "$(pwd):/app/backend" \
    -w /app/backend \
    -e DATABASE_URL="$DATABASE_URL" \
    python:3.11-slim \
    sh -c "pip install --quiet --no-cache-dir -r requirements.txt && python -m alembic upgrade head"

echo "✅ Migrations completate!"

