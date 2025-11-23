#!/bin/bash
# Script per ripristinare backup di ChromaDB locale

set -e

if [ -z "$1" ]; then
    echo "❌ Uso: $0 <path-to-backup>"
    echo "   Esempio: $0 backups/chromadb/chromadb-backup-20251123-200000"
    exit 1
fi

BACKUP_PATH="$1"

if [ ! -d "$BACKUP_PATH" ]; then
    echo "❌ Directory backup non trovata: $BACKUP_PATH"
    exit 1
fi

if [ ! -f "$BACKUP_PATH/chroma.sqlite3" ]; then
    echo "❌ Backup non valido: chroma.sqlite3 non trovato"
    exit 1
fi

echo "🔄 Ripristino backup ChromaDB da: $BACKUP_PATH"

# Ferma il container (se in esecuzione)
if docker ps | grep -q knowledge-navigator-chromadb; then
    echo "⏸️  Fermando container ChromaDB..."
    docker stop knowledge-navigator-chromadb
    docker rm knowledge-navigator-chromadb
    sleep 2
fi

# Trova il nome del volume
VOLUME_NAME=""
if docker volume ls | grep -q "personalaiassistant_chromadb_data"; then
    VOLUME_NAME="personalaiassistant_chromadb_data"
elif docker volume ls | grep -q "knowledge-navigator_chromadb_data"; then
    VOLUME_NAME="knowledge-navigator_chromadb_data"
else
    echo "⚠️  Volume non trovato, verrà creato automaticamente"
    VOLUME_NAME="personalaiassistant_chromadb_data"
fi

# Rimuovi volume esistente (ATTENZIONE: perdi i dati attuali!)
read -p "⚠️  Questo rimuoverà i dati attuali. Continuare? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Operazione annullata"
    exit 1
fi

echo "🗑️  Rimuovendo volume esistente: $VOLUME_NAME..."
docker volume rm "$VOLUME_NAME" 2>/dev/null || true

# Crea nuovo volume e ripristina dati
echo "📋 Ripristinando dati..."
docker run --rm \
    -v "$VOLUME_NAME":/data \
    -v "$BACKUP_PATH":/backup:ro \
    alpine:latest \
    sh -c "cp -r /backup/* /data/ && chown -R 1000:1000 /data"

echo "✅ Ripristino completato"
echo "🚀 Riavvia ChromaDB con: docker-compose up -d chromadb"

