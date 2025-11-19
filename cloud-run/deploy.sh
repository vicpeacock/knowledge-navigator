#!/bin/bash
# Script per deploy su Google Cloud Run
# Usage: ./cloud-run/deploy.sh [backend|frontend|all]

set -e

PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
REGION="${GCP_REGION:-us-central1}"
BACKEND_SERVICE="knowledge-navigator-backend"
FRONTEND_SERVICE="knowledge-navigator-frontend"

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

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
        log_error "gcloud CLI non trovato. Installa Google Cloud SDK: https://cloud.google.com/sdk/docs/install"
        exit 1
    fi
}

function check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker non trovato. Installa Docker: https://docs.docker.com/get-docker/"
        exit 1
    fi
}

function build_backend() {
    log_info "Building backend Docker image with Gemini support..."
    # Use requirements-cloud.txt for cloud deployment (includes Gemini SDK)
    docker build \
        -f Dockerfile.backend \
        --build-arg REQUIREMENTS_FILE=requirements-cloud.txt \
        -t gcr.io/${PROJECT_ID}/${BACKEND_SERVICE}:latest .
    docker tag gcr.io/${PROJECT_ID}/${BACKEND_SERVICE}:latest gcr.io/${PROJECT_ID}/${BACKEND_SERVICE}:$(date +%Y%m%d-%H%M%S)
}

function push_backend() {
    log_info "Pushing backend image to Google Container Registry..."
    docker push gcr.io/${PROJECT_ID}/${BACKEND_SERVICE}:latest
}

function deploy_backend() {
    log_info "Deploying backend to Cloud Run with Gemini..."
    
    # Check if GEMINI_API_KEY is set
    if [ -z "$GEMINI_API_KEY" ]; then
        log_warn "GEMINI_API_KEY not set. Set it as a Cloud Run secret or env var."
        log_info "Get API key from: https://aistudio.google.com/app/apikey"
    fi
    
    # Build env vars for Cloud Run
    ENV_VARS="PORT=8000,LLM_PROVIDER=gemini"
    if [ -n "$GEMINI_API_KEY" ]; then
        ENV_VARS="${ENV_VARS},GEMINI_API_KEY=${GEMINI_API_KEY}"
    fi
    if [ -n "$GEMINI_MODEL" ]; then
        ENV_VARS="${ENV_VARS},GEMINI_MODEL=${GEMINI_MODEL}"
    fi
    
    gcloud run deploy ${BACKEND_SERVICE} \
        --image gcr.io/${PROJECT_ID}/${BACKEND_SERVICE}:latest \
        --platform managed \
        --region ${REGION} \
        --allow-unauthenticated \
        --port 8000 \
        --memory 2Gi \
        --cpu 2 \
        --timeout 300 \
        --max-instances 10 \
        --set-env-vars "${ENV_VARS}" \
        --add-cloudsql-instances ${PROJECT_ID}:${REGION}:knowledge-navigator-db || log_warn "Cloud SQL instance non configurato. Usa database esterno."
    
    log_info "Backend deployed with Gemini LLM provider"
    log_info "Make sure to set GEMINI_API_KEY as Cloud Run secret or env var if not already set"
}

function build_frontend() {
    log_info "Building frontend Docker image..."
    docker build -f Dockerfile.frontend -t gcr.io/${PROJECT_ID}/${FRONTEND_SERVICE}:latest .
    docker tag gcr.io/${PROJECT_ID}/${FRONTEND_SERVICE}:latest gcr.io/${PROJECT_ID}/${FRONTEND_SERVICE}:$(date +%Y%m%d-%H%M%S)
}

function push_frontend() {
    log_info "Pushing frontend image to Google Container Registry..."
    docker push gcr.io/${PROJECT_ID}/${FRONTEND_SERVICE}:latest
}

function deploy_frontend() {
    log_info "Deploying frontend to Cloud Run..."
    
    # Ottieni URL backend (se deployato)
    BACKEND_URL=$(gcloud run services describe ${BACKEND_SERVICE} --region ${REGION} --format 'value(status.url)' 2>/dev/null || echo "")
    
    if [ -z "$BACKEND_URL" ]; then
        log_warn "Backend URL non trovato. Configura NEXT_PUBLIC_API_URL manualmente."
        BACKEND_URL="https://${BACKEND_SERVICE}-${REGION}-${PROJECT_ID}.a.run.app"
    fi
    
    gcloud run deploy ${FRONTEND_SERVICE} \
        --image gcr.io/${PROJECT_ID}/${FRONTEND_SERVICE}:latest \
        --platform managed \
        --region ${REGION} \
        --allow-unauthenticated \
        --port 3000 \
        --memory 512Mi \
        --cpu 1 \
        --timeout 60 \
        --max-instances 5 \
        --set-env-vars "PORT=3000,NEXT_PUBLIC_API_URL=${BACKEND_URL}"
}

function main() {
    check_gcloud
    check_docker
    
    # Verifica che PROJECT_ID sia configurato
    if [ "$PROJECT_ID" = "your-project-id" ]; then
        log_error "Configura GCP_PROJECT_ID: export GCP_PROJECT_ID=your-actual-project-id"
        exit 1
    fi
    
    # Configura Docker per GCR
    log_info "Configurando Docker per Google Container Registry..."
    gcloud auth configure-docker
    
    DEPLOY_TARGET="${1:-all}"
    
    case $DEPLOY_TARGET in
        backend)
            build_backend
            push_backend
            deploy_backend
            ;;
        frontend)
            build_frontend
            push_frontend
            deploy_frontend
            ;;
        all)
            log_info "Deploying both backend and frontend..."
            build_backend
            push_backend
            deploy_backend
            sleep 5  # Attendi che backend sia disponibile
            build_frontend
            push_frontend
            deploy_frontend
            ;;
        *)
            log_error "Usage: $0 [backend|frontend|all]"
            exit 1
            ;;
    esac
    
    log_info "Deployment completato!"
    log_info "Backend URL: $(gcloud run services describe ${BACKEND_SERVICE} --region ${REGION} --format 'value(status.url)' 2>/dev/null || echo 'N/A')"
    log_info "Frontend URL: $(gcloud run services describe ${FRONTEND_SERVICE} --region ${REGION} --format 'value(status.url)' 2>/dev/null || echo 'N/A')"
}

main "$@"

