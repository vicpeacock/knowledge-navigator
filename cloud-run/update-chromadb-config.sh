#!/bin/bash
# Script per aggiornare configurazione ChromaDB in .env.cloud-run dopo deployment

set -e

PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
REGION="${GCP_REGION:-us-central1}"
CHROMADB_SERVICE="knowledge-navigator-chromadb"

if [ "$PROJECT_ID" = "your-project-id" ]; then
    echo "❌ Configura GCP_PROJECT_ID: export GCP_PROJECT_ID=your-actual-project-id"
    exit 1
fi

# Ottieni URL ChromaDB
CHROMADB_URL=$(gcloud run services describe ${CHROMADB_SERVICE} \
    --region ${REGION} \
    --format 'value(status.url)' 2>/dev/null || echo "")

if [ -z "$CHROMADB_URL" ]; then
    echo "❌ ChromaDB service non trovato. Deploy prima ChromaDB: ./cloud-run/deploy-chromadb.sh"
    exit 1
fi

# Estrai host (rimuovi https:// e path)
CHROMADB_HOST=$(echo ${CHROMADB_URL} | sed 's|https\?://||' | cut -d'/' -f1)

echo "✅ ChromaDB URL: ${CHROMADB_URL}"
echo "✅ ChromaDB Host: ${CHROMADB_HOST}"
echo ""

# Aggiorna .env.cloud-run
if [ -f ".env.cloud-run" ]; then
    # Backup
    cp .env.cloud-run .env.cloud-run.backup
    
    # Aggiorna CHROMADB_HOST e CHROMADB_PORT
    sed -i.bak "s|^CHROMADB_HOST=.*|CHROMADB_HOST=${CHROMADB_HOST}|" .env.cloud-run
    sed -i.bak "s|^CHROMADB_PORT=.*|CHROMADB_PORT=443|" .env.cloud-run
    
    # Rimuovi backup
    rm -f .env.cloud-run.bak
    
    echo "✅ File .env.cloud-run aggiornato!"
    echo ""
    echo "📝 Configurazione ChromaDB:"
    grep "^CHROMADB_" .env.cloud-run
else
    echo "❌ File .env.cloud-run non trovato!"
    exit 1
fi

