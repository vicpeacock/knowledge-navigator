#!/bin/bash
# Script per aggiornare ChromaDB locale mantenendo i dati

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "🔄 Aggiornamento ChromaDB locale..."

# 1. Backup dei dati
echo "📦 Step 1: Backup dati esistenti..."
./scripts/backup-chromadb.sh

if [ $? -ne 0 ]; then
    echo "❌ Backup fallito. Interrompo l'aggiornamento."
    exit 1
fi

# 2. Ferma il container
echo ""
echo "⏸️  Step 2: Fermando container ChromaDB..."
docker-compose stop chromadb
docker-compose rm -f chromadb

# 3. Aggiorna docker-compose.yml
echo ""
echo "📝 Step 3: Aggiornando docker-compose.yml..."
# Backup del file originale
cp docker-compose.yml docker-compose.yml.backup

# Aggiorna la versione (usa una versione recente ma stabile)
# Nota: Il salto da 0.4.18 a 1.x potrebbe richiedere migrazione dati
# Usiamo una versione intermedia per sicurezza
sed -i.bak 's|chromadb/chroma:0.4.18|chromadb/chroma:0.5.0|g' docker-compose.yml

echo "   ✅ Aggiornato a chromadb/chroma:0.5.0"

# 4. Riavvia con nuova versione
echo ""
echo "🚀 Step 4: Riavviando ChromaDB con nuova versione..."
docker-compose pull chromadb
docker-compose up -d chromadb

# 5. Attendi che sia ready
echo ""
echo "⏳ Step 5: Attendo che ChromaDB sia ready..."
sleep 5

MAX_RETRIES=30
RETRY=0
while [ $RETRY -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:8001/api/v1/heartbeat > /dev/null 2>&1; then
        echo "✅ ChromaDB è ready!"
        break
    fi
    RETRY=$((RETRY + 1))
    echo "   Tentativo $RETRY/$MAX_RETRIES..."
    sleep 2
done

if [ $RETRY -eq $MAX_RETRIES ]; then
    echo "❌ ChromaDB non risponde. Verifica i log: docker logs knowledge-navigator-chromadb"
    echo "   Per ripristinare: ./scripts/restore-chromadb.sh backups/chromadb/chromadb-backup-*"
    exit 1
fi

# 6. Verifica che i dati siano ancora accessibili
echo ""
echo "🔍 Step 6: Verificando accesso ai dati..."
# Prova a connettersi con il client Python
python3 -c "
import chromadb
try:
    client = chromadb.HttpClient(host='localhost', port=8001)
    collections = client.list_collections()
    print(f'✅ Trovate {len(collections)} collezioni')
    for col in collections:
        print(f'   - {col.name}')
except Exception as e:
    print(f'❌ Errore: {e}')
    exit(1)
" 2>&1

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Aggiornamento completato con successo!"
    echo "📋 Backup salvato in: backups/chromadb/"
else
    echo ""
    echo "⚠️  Problemi nell'accesso ai dati. Verifica i log."
    echo "   Per ripristinare: ./scripts/restore-chromadb.sh backups/chromadb/chromadb-backup-*"
fi

