#!/bin/bash
# Script per recuperare dati da Supabase e ripristinarli localmente

set -e

# Database cloud (Supabase)
CLOUD_DB="db.zdyuqekimdpsmnelzvri.supabase.co"
CLOUD_USER="postgres"
CLOUD_PASS="PllVcn_66.superbase"
CLOUD_DB_NAME="postgres"

# Database locale
LOCAL_HOST="localhost"
LOCAL_PORT="5432"
LOCAL_USER="knavigator"
LOCAL_PASS="knavigator_pass"
LOCAL_DB="knowledge_navigator"

echo "🔄 Esportazione dati dal cloud Supabase..."
echo "=========================================="

# Export con pg_dump usando Docker (se pg_dump non è installato)
if command -v pg_dump &> /dev/null; then
    export PGPASSWORD="$CLOUD_PASS"
    pg_dump -h "$CLOUD_DB" -p 5432 -U "$CLOUD_USER" -d "$CLOUD_DB_NAME" \
        --schema=public \
        --data-only \
        --table=tenants \
        --table=users \
        --table=sessions \
        --table=messages \
        --table=integrations \
        --table=files \
        --table=notifications \
        -F p \
        > /tmp/knowledge_navigator_export.sql
else
    echo "Usando Docker per eseguire pg_dump..."
    docker run --rm -e PGPASSWORD="$CLOUD_PASS" postgres:16-alpine pg_dump \
        -h "$CLOUD_DB" -p 5432 -U "$CLOUD_USER" -d "$CLOUD_DB_NAME" \
        --schema=public \
        --data-only \
        --table=tenants \
        --table=users \
        --table=sessions \
        --table=messages \
        --table=integrations \
        --table=files \
        --table=notifications \
        -F p \
        > /tmp/knowledge_navigator_export.sql
fi

echo "✅ Export completato: /tmp/knowledge_navigator_export.sql"
echo ""
echo "📥 Importazione nel database locale..."
echo "====================================="

# Import nel database locale
if command -v psql &> /dev/null; then
    export PGPASSWORD="$LOCAL_PASS"
    psql -h "$LOCAL_HOST" -p "$LOCAL_PORT" -U "$LOCAL_USER" -d "$LOCAL_DB" \
        -f /tmp/knowledge_navigator_export.sql
else
    echo "Usando Docker per eseguire psql..."
    docker exec -i knowledge-navigator-postgres psql -U "$LOCAL_USER" -d "$LOCAL_DB" \
        < /tmp/knowledge_navigator_export.sql
fi

echo ""
echo "✅ Restore completato!"
echo "   I dati sono stati ripristinati nel database locale."

