#!/bin/bash
# Script per deploy ChromaDB su Google Cloud Run

set -e

PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
REGION="${GCP_REGION:-us-central1}"
CHROMADB_SERVICE="knowledge-navigator-chromadb"

# Colori
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

function log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

function log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

function log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

function check_gcloud() {
    if ! command -v gcloud &> /dev/null; then
        log_error "gcloud CLI non trovato. Installa Google Cloud SDK"
        exit 1
    fi
}

function check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker non trovato"
        exit 1
    fi
}

function build_chromadb() {
    log_info "Building ChromaDB Docker image..."
    docker build \
        -f Dockerfile.chromadb \
        -t gcr.io/${PROJECT_ID}/${CHROMADB_SERVICE}:latest .
    docker tag gcr.io/${PROJECT_ID}/${CHROMADB_SERVICE}:latest \
        gcr.io/${PROJECT_ID}/${CHROMADB_SERVICE}:$(date +%Y%m%d-%H%M%S)
}

function push_chromadb() {
    log_info "Pushing ChromaDB image to Google Container Registry..."
    docker push gcr.io/${PROJECT_ID}/${CHROMADB_SERVICE}:latest
}

function deploy_chromadb() {
    log_info "Deploying ChromaDB to Cloud Run..."
    
    gcloud run deploy ${CHROMADB_SERVICE} \
        --image gcr.io/${PROJECT_ID}/${CHROMADB_SERVICE}:latest \
        --platform managed \
        --region ${REGION} \
        --allow-unauthenticated \
        --port 8000 \
        --memory 1Gi \
        --cpu 1 \
        --timeout 300 \
        --max-instances 5 \
        --set-env-vars "IS_PERSISTENT=TRUE"
    
    log_info "ChromaDB deployed successfully!"
    
    # Ottieni URL
    CHROMADB_URL=$(gcloud run services describe ${CHROMADB_SERVICE} \
        --region ${REGION} \
        --format 'value(status.url)')
    
    log_info "ChromaDB URL: ${CHROMADB_URL}"
    log_info ""
    log_info "⚠️  IMPORTANTE: Aggiorna .env.cloud-run con:"
    log_info "   CHROMADB_HOST=$(echo ${CHROMADB_URL} | sed 's|https\?://||' | cut -d'/' -f1)"
    log_info "   CHROMADB_PORT=443"
    log_info ""
    log_info "   Oppure usa l'URL completo senza porta:"
    log_info "   CHROMADB_HOST=${CHROMADB_URL#https://}"
}

function main() {
    check_gcloud
    check_docker
    
    if [ "$PROJECT_ID" = "your-project-id" ]; then
        log_error "Configura GCP_PROJECT_ID: export GCP_PROJECT_ID=your-actual-project-id"
        exit 1
    fi
    
    # Configura Docker per GCR
    log_info "Configurando Docker per Google Container Registry..."
    gcloud auth configure-docker
    
    build_chromadb
    push_chromadb
    deploy_chromadb
}

main "$@"

