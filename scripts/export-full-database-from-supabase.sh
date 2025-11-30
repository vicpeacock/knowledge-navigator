#!/bin/bash
# Script per fare un DUMP COMPLETO del database Supabase
# Esporta TUTTO: users, sessions, messages, files, memory, integrations, notifications, ecc.

set -e

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔄 Export COMPLETO del database Supabase"
echo "=========================================="
echo ""

# Carica variabili d'ambiente dal .env.cloud-run
if [ -f ".env.cloud-run" ]; then
    export $(grep -v '^#' .env.cloud-run | grep -v '^$' | xargs)
else
    echo -e "${RED}❌ Errore: File .env.cloud-run non trovato.${NC}"
    exit 1
fi

# Estrai i componenti della DATABASE_URL di Supabase
# Formato: postgresql+asyncpg://postgres:PASSWORD@db.PROJECT_ID.supabase.co:5432/postgres
DATABASE_URL=${DATABASE_URL}

if [ -z "$DATABASE_URL" ]; then
    echo -e "${RED}❌ Errore: DATABASE_URL non trovato in .env.cloud-run${NC}"
    exit 1
fi

# Estrai password (potrebbe essere in DATABASE_URL o POSTGRES_PASSWORD)
if [ -n "$POSTGRES_PASSWORD" ]; then
    SUPABASE_PASSWORD="$POSTGRES_PASSWORD"
else
    # Prova a estrarre dalla DATABASE_URL
    SUPABASE_PASSWORD=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
fi

# Estrai altri componenti dalla DATABASE_URL
SUPABASE_USER=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/\([^:]*\):.*@.*/\1/p')
SUPABASE_HOST=$(echo "$DATABASE_URL" | sed -n 's/.*@\([^:]*\):.*/\1/p')
SUPABASE_PORT=$(echo "$DATABASE_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
SUPABASE_DB=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/[^/]*\/\(.*\)/\1/p' | sed 's/?.*//')

# Se non riusciti ad estrarre, usa valori di default per Supabase
if [ -z "$SUPABASE_USER" ]; then
    SUPABASE_USER="postgres"
fi
if [ -z "$SUPABASE_HOST" ]; then
    echo -e "${RED}❌ Errore: Impossibile estrarre SUPABASE_HOST dalla DATABASE_URL${NC}"
    exit 1
fi
if [ -z "$SUPABASE_PORT" ]; then
    SUPABASE_PORT="5432"
fi
if [ -z "$SUPABASE_DB" ]; then
    SUPABASE_DB="postgres"
fi

if [ -z "$SUPABASE_PASSWORD" ]; then
    echo -e "${RED}❌ Errore: Password non trovata.${NC}"
    echo "   Verifica che POSTGRES_PASSWORD o DATABASE_URL contengano la password."
    exit 1
fi

DUMP_FILE="supabase_full_backup_$(date +%Y%m%d_%H%M%S).sql"

echo "📋 Configurazione Supabase:"
echo "   User: $SUPABASE_USER"
echo "   Host: $SUPABASE_HOST"
echo "   Port: $SUPABASE_PORT"
echo "   Database: $SUPABASE_DB"
echo "   Password: (hidden)"
echo ""

echo "📦 Creazione dump completo del database..."
echo "   Questo può richiedere alcuni minuti se il database è grande..."

# Usa Docker per eseguire pg_dump (più semplice che installare tutto localmente)
docker run --rm \
    -e PGPASSWORD="$SUPABASE_PASSWORD" \
    postgres:16-alpine \
    pg_dump \
    -h "$SUPABASE_HOST" \
    -p "$SUPABASE_PORT" \
    -U "$SUPABASE_USER" \
    -d "$SUPABASE_DB" \
    --format=plain \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges \
    --verbose \
    > "$DUMP_FILE"

if [ $? -eq 0 ]; then
    DUMP_SIZE=$(du -h "$DUMP_FILE" | cut -f1)
    echo -e "${GREEN}✅ Dump completato!${NC}"
    echo "   File: $DUMP_FILE"
    echo "   Dimensione: $DUMP_SIZE"
    echo ""
    echo "📥 Ora puoi importare questo dump nel database locale:"
    echo "   docker exec -i knowledge-navigator-postgres psql -U knavigator -d knowledge_navigator < $DUMP_FILE"
    echo ""
    echo "   Oppure:"
    echo "   PGPASSWORD=knavigator_pass psql -h localhost -p 5432 -U knavigator -d knowledge_navigator < $DUMP_FILE"
else
    echo -e "${RED}❌ Errore durante il dump.${NC}"
    exit 1
fi

