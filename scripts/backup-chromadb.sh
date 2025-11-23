#!/bin/bash
# Script per fare backup di ChromaDB locale prima dell'aggiornamento

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${PROJECT_ROOT}/backups/chromadb"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_PATH="${BACKUP_DIR}/chromadb-backup-${TIMESTAMP}"

echo "📦 Backup ChromaDB locale..."

# Crea directory backup
mkdir -p "$BACKUP_PATH"

# Ferma il container (se in esecuzione)
if docker ps | grep -q knowledge-navigator-chromadb; then
    echo "⏸️  Fermando container ChromaDB..."
    docker stop knowledge-navigator-chromadb
    sleep 2
fi

# Copia i dati dal volume (prova entrambi i nomi possibili)
VOLUME_NAME=""
if docker volume ls | grep -q "personalaiassistant_chromadb_data"; then
    VOLUME_NAME="personalaiassistant_chromadb_data"
elif docker volume ls | grep -q "knowledge-navigator_chromadb_data"; then
    VOLUME_NAME="knowledge-navigator_chromadb_data"
else
    echo "❌ Volume ChromaDB non trovato"
    exit 1
fi

echo "📋 Copiando dati dal volume: $VOLUME_NAME..."
docker run --rm \
    -v "$VOLUME_NAME":/data:ro \
    -v "$BACKUP_PATH":/backup \
    alpine:latest \
    sh -c "cp -r /data/* /backup/"

# Verifica backup
if [ -f "$BACKUP_PATH/chroma.sqlite3" ]; then
    echo "✅ Backup completato: $BACKUP_PATH"
    echo "   File: chroma.sqlite3"
    echo "   Collezioni: $(ls -d $BACKUP_PATH/*/ 2>/dev/null | wc -l | tr -d ' ')"
    du -sh "$BACKUP_PATH"
else
    echo "❌ Errore: backup non valido"
    exit 1
fi

echo ""
echo "💾 Backup salvato in: $BACKUP_PATH"
echo "   Per ripristinare: ./scripts/restore-chromadb.sh $BACKUP_PATH"

