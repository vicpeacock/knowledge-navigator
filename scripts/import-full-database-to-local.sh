#!/bin/bash
# Script per importare un dump SQL completo nel database locale
# Questo script prende il dump creato da download-full-database-dump.sh
# e lo importa nel database PostgreSQL locale

set -e

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "📥 Importazione dump completo nel database locale"
echo "=================================================="
echo ""

# Accetta file dump come parametro, oppure cerca il più recente
if [ -n "$1" ]; then
    DUMP_FILE="$1"
else
    # Cerca il file dump più recente
    DUMP_FILE=$(ls -t knowledge_navigator_full_backup_*.sql supabase_full_backup_*.sql 2>/dev/null | head -1)
fi

if [ -z "$DUMP_FILE" ] || [ ! -f "$DUMP_FILE" ]; then
    echo -e "${RED}❌ Nessun file dump trovato.${NC}"
    echo "   Usa: $0 <dump_file.sql>"
    echo "   Oppure crea prima il dump con: ./scripts/download-full-database-dump.sh"
    exit 1
fi

echo "📋 File dump trovato: $DUMP_FILE"
DUMP_SIZE=$(du -h "$DUMP_FILE" | cut -f1)
echo "   Dimensione: $DUMP_SIZE"
echo ""

read -p "⚠️  Questo sovrascriverà il database locale. Continuare? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Operazione annullata"
    exit 1
fi

echo ""
echo "🔄 Importazione in corso..."
echo "   (Questo può richiedere alcuni minuti...)"
echo ""

# Importa usando Docker (se il container postgres è attivo)
if docker ps | grep -q "knowledge-navigator-postgres"; then
    echo "   Usando Docker container..."
    docker exec -i knowledge-navigator-postgres psql -U knavigator -d knowledge_navigator < "$DUMP_FILE"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Importazione completata!${NC}"
    else
        echo -e "${RED}❌ Errore durante l'importazione.${NC}"
        exit 1
    fi
else
    # Prova con psql diretto
    echo "   Usando psql diretto..."
    PGPASSWORD=knavigator_pass psql -h localhost -p 5432 -U knavigator -d knowledge_navigator < "$DUMP_FILE"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Importazione completata!${NC}"
    else
        echo -e "${RED}❌ Errore durante l'importazione.${NC}"
        echo "   Assicurati che PostgreSQL sia in esecuzione e accessibile."
        exit 1
    fi
fi

echo ""
echo "🎉 Database locale aggiornato con tutti i dati dal cloud!"

