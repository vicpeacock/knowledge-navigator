#!/bin/bash
# Script per costruire la connection string Supabase manualmente

set -e

echo "🔧 Costruzione Connection String Supabase"
echo "=========================================="
echo ""

# Informazioni progetto (già note)
PROJECT_REF="${SUPABASE_PROJECT_ID:-[PROJECT_ID]}"
DB_HOST="db.${PROJECT_REF}.supabase.co"
DB_PORT="5432"
DB_USER="postgres"
DB_NAME="postgres"

echo "📋 Informazioni Progetto:"
echo "   Host: ${DB_HOST}"
echo "   Port: ${DB_PORT}"
echo "   User: ${DB_USER}"
echo "   Database: ${DB_NAME}"
echo ""

# Chiedi password all'utente
echo "🔐 Password Database:"
echo "   Se non ricordi la password, puoi resettarla:"
echo "   1. Vai su: https://app.supabase.com/project/${PROJECT_REF}/settings/database"
echo "   2. Cerca 'Database password' o 'Reset database password'"
echo "   3. Genera una nuova password e SALVALA"
echo ""
read -sp "Inserisci la password del database: " DB_PASSWORD
echo ""

# Costruisci connection string
CONNECTION_STRING="postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

echo ""
echo "✅ Connection String generata:"
echo "   ${CONNECTION_STRING}"
echo ""

# Aggiorna .env.cloud-run
if [ -f ".env.cloud-run" ]; then
    # Backup
    cp .env.cloud-run .env.cloud-run.backup
    
    # Sostituisci DATABASE_URL
    sed -i.bak "s|^DATABASE_URL=.*|DATABASE_URL=${CONNECTION_STRING}|" .env.cloud-run
    
    # Sostituisci POSTGRES_PASSWORD
    sed -i.bak "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${DB_PASSWORD}|" .env.cloud-run
    
    # Sostituisci POSTGRES_HOST
    sed -i.bak "s|^POSTGRES_HOST=.*|POSTGRES_HOST=${DB_HOST}|" .env.cloud-run
    
    # Rimuovi file backup
    rm -f .env.cloud-run.bak
    
    echo "✅ File .env.cloud-run aggiornato!"
    echo ""
    echo "📝 Verifica:"
    echo "   DATABASE_URL: ${CONNECTION_STRING:0:50}..."
    echo "   POSTGRES_PASSWORD: ${DB_PASSWORD:0:10}..."
    echo ""
else
    echo "⚠️  File .env.cloud-run non trovato!"
    echo "   Esegui prima: ./scripts/create-cloud-env.sh"
    exit 1
fi

echo "✅ Configurazione database completata!"
echo ""

