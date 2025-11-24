#!/bin/bash
# Enhanced deployment script for Google Cloud Run
# Loads all environment variables from .env.cloud-run
# Usage: ./cloud-run/deploy-enhanced.sh [backend|frontend|all]

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env.cloud-run"

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

function log_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $1"
}

function check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command -v gcloud &> /dev/null; then
        log_error "gcloud CLI non trovato. Installa Google Cloud SDK: https://cloud.google.com/sdk/docs/install"
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker non trovato. Installa Docker: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    if [ ! -f "$ENV_FILE" ]; then
        log_error "File .env.cloud-run non trovato in: $ENV_FILE"
        log_info "Crea il file .env.cloud-run basandoti su cloud-run/env.example"
        exit 1
    fi
    
    log_info "✅ Prerequisites check passed"
}

function check_syntax() {
    log_info "Checking Python syntax before deployment..."
    
    ERRORS=0
    while IFS= read -r -d '' file; do
        if ! python3 -m py_compile "$file" 2>/dev/null; then
            log_error "Syntax error in: $file"
            ERRORS=$((ERRORS + 1))
        fi
    done < <(find "$PROJECT_ROOT/backend/app" -name "*.py" -type f -print0 2>/dev/null)
    
    if [ $ERRORS -gt 0 ]; then
        log_error "Found $ERRORS file(s) with syntax errors. Fix them before deploying."
        exit 1
    fi
    
    log_info "✅ All Python files have valid syntax"
}

function load_env_file() {
    log_info "Loading environment variables from .env.cloud-run..."
    
    if [ ! -f "$ENV_FILE" ]; then
        log_error "File .env.cloud-run non trovato"
        exit 1
    fi
    
    # Load .env.cloud-run file, handling values with spaces
    # Use eval to properly handle quoted values
    while IFS= read -r line || [ -n "$line" ]; do
        # Skip empty lines and comments
        [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
        
        # Skip lines without =
        [[ ! "$line" =~ = ]] && continue
        
        # Remove leading/trailing whitespace
        line=$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        
        # Extract key and value
        key=$(echo "$line" | cut -d'=' -f1 | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        value=$(echo "$line" | cut -d'=' -f2- | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
        
        # Remove quotes if present
        value=$(echo "$value" | sed 's/^"//;s/"$//;s/^'"'"'//;s/'"'"'$//')
        
        # Export the variable
        export "$key=$value" 2>/dev/null || true
    done < "$ENV_FILE"
    
    log_info "✅ Environment variables loaded"
}

function check_gcp_project() {
    log_info "Checking GCP project configuration..."
    
    # Check if GCP_PROJECT_ID is set
    if [ -z "$GCP_PROJECT_ID" ]; then
        CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")
        if [ -n "$CURRENT_PROJECT" ]; then
            export GCP_PROJECT_ID="$CURRENT_PROJECT"
            log_info "Using current GCP project: $GCP_PROJECT_ID"
        else
            log_error "GCP_PROJECT_ID non configurato. Imposta: export GCP_PROJECT_ID=your-project-id"
            exit 1
        fi
    else
        log_info "Using GCP_PROJECT_ID: $GCP_PROJECT_ID"
        gcloud config set project "$GCP_PROJECT_ID"
    fi
    
    # Verify project exists
    if ! gcloud projects describe "$GCP_PROJECT_ID" &>/dev/null; then
        log_error "Progetto GCP '$GCP_PROJECT_ID' non trovato o non accessibile"
        exit 1
    fi
    
    log_info "✅ GCP project verified: $GCP_PROJECT_ID"
}

function enable_apis() {
    log_info "Enabling required GCP APIs..."
    
    gcloud services enable run.googleapis.com --quiet
    gcloud services enable containerregistry.googleapis.com --quiet
    gcloud services enable secretmanager.googleapis.com --quiet
    
    log_info "✅ GCP APIs enabled"
}

function configure_docker() {
    log_info "Configuring Docker for Google Container Registry..."
    gcloud auth configure-docker --quiet
    log_info "✅ Docker configured"
}

function build_env_vars_string() {
    # Build environment variables string for Cloud Run
    # Exclude sensitive/complex vars that should be secrets
    # Note: PORT is automatically set by Cloud Run, don't include it
    ENV_VARS=""
    
    # LLM Provider (required)
    if [ -n "$LLM_PROVIDER" ]; then
        ENV_VARS="LLM_PROVIDER=${LLM_PROVIDER}"
    else
        ENV_VARS="LLM_PROVIDER=gemini"
    fi
    
    # Helper function to add env var
    add_env_var() {
        local key="$1"
        local value="$2"
        if [ -n "$value" ]; then
            if [ -n "$ENV_VARS" ]; then
                ENV_VARS="${ENV_VARS},${key}=${value}"
            else
                ENV_VARS="${key}=${value}"
            fi
        fi
    }
    
    # Gemini
    add_env_var "GEMINI_API_KEY" "$GEMINI_API_KEY"
    add_env_var "GEMINI_MODEL" "$GEMINI_MODEL"
    
    # Database
    add_env_var "DATABASE_URL" "$DATABASE_URL"
    add_env_var "POSTGRES_HOST" "$POSTGRES_HOST"
    add_env_var "POSTGRES_USER" "$POSTGRES_USER"
    add_env_var "POSTGRES_PASSWORD" "$POSTGRES_PASSWORD"
    add_env_var "POSTGRES_DB" "$POSTGRES_DB"
    add_env_var "POSTGRES_PORT" "$POSTGRES_PORT"
    
    # ChromaDB Cloud
    add_env_var "CHROMADB_USE_CLOUD" "$CHROMADB_USE_CLOUD"
    add_env_var "CHROMADB_CLOUD_API_KEY" "$CHROMADB_CLOUD_API_KEY"
    add_env_var "CHROMADB_CLOUD_TENANT" "$CHROMADB_CLOUD_TENANT"
    add_env_var "CHROMADB_CLOUD_DATABASE" "$CHROMADB_CLOUD_DATABASE"
    
    # Security Keys
    add_env_var "SECRET_KEY" "$SECRET_KEY"
    add_env_var "ENCRYPTION_KEY" "$ENCRYPTION_KEY"
    add_env_var "JWT_SECRET_KEY" "$JWT_SECRET_KEY"
    
    # Google OAuth (for Gmail/Calendar integrations)
    add_env_var "GOOGLE_CLIENT_ID" "$GOOGLE_CLIENT_ID"
    add_env_var "GOOGLE_CLIENT_SECRET" "$GOOGLE_CLIENT_SECRET"
    
    # Google OAuth for Workspace MCP (for Google Workspace MCP server OAuth)
    add_env_var "GOOGLE_OAUTH_CLIENT_ID" "$GOOGLE_OAUTH_CLIENT_ID"
    add_env_var "GOOGLE_OAUTH_CLIENT_SECRET" "$GOOGLE_OAUTH_CLIENT_SECRET"
    
    # Google Custom Search
    add_env_var "GOOGLE_PSE_API_KEY" "$GOOGLE_PSE_API_KEY"
    add_env_var "GOOGLE_PSE_CX" "$GOOGLE_PSE_CX"
    
    # Other settings
    add_env_var "USE_LANGGRAPH_PROTOTYPE" "$USE_LANGGRAPH_PROTOTYPE"
    
    echo "$ENV_VARS"
}

function build_backend() {
    log_info "Building backend Docker image..."
    
    cd "$PROJECT_ROOT"
    
    # Use requirements-cloud.txt if it exists, otherwise requirements.txt
    REQUIREMENTS_FILE="requirements.txt"
    if [ -f "requirements-cloud.txt" ]; then
        REQUIREMENTS_FILE="requirements-cloud.txt"
        log_info "Using requirements-cloud.txt for cloud deployment"
    fi
    
    docker build \
        --platform linux/amd64 \
        -f Dockerfile.backend \
        --build-arg REQUIREMENTS_FILE="$REQUIREMENTS_FILE" \
        -t gcr.io/${GCP_PROJECT_ID}/knowledge-navigator-backend:latest .
    
    docker tag gcr.io/${GCP_PROJECT_ID}/knowledge-navigator-backend:latest \
        gcr.io/${GCP_PROJECT_ID}/knowledge-navigator-backend:$(date +%Y%m%d-%H%M%S)
    
    log_info "✅ Backend image built"
}

function push_backend() {
    log_info "Pushing backend image to Google Container Registry..."
    docker push gcr.io/${GCP_PROJECT_ID}/knowledge-navigator-backend:latest
    log_info "✅ Backend image pushed"
}

function deploy_backend() {
    log_info "Deploying backend to Cloud Run..."
    
    REGION="${GCP_REGION:-us-central1}"
    ENV_VARS=$(build_env_vars_string)
    
    log_debug "Environment variables: ${ENV_VARS:0:200}..."
    
    gcloud run deploy knowledge-navigator-backend \
        --image gcr.io/${GCP_PROJECT_ID}/knowledge-navigator-backend:latest \
        --platform managed \
        --region "$REGION" \
        --allow-unauthenticated \
        --port 8000 \
        --memory 2Gi \
        --cpu 2 \
        --timeout 300 \
        --max-instances 10 \
        --set-env-vars "$ENV_VARS"
    
    BACKEND_URL=$(gcloud run services describe knowledge-navigator-backend \
        --region "$REGION" \
        --format 'value(status.url)')
    
    log_info "✅ Backend deployed: $BACKEND_URL"
    echo "$BACKEND_URL"
}

function build_frontend() {
    log_info "Building frontend Docker image..."
    
    cd "$PROJECT_ROOT"
    
    # Get backend URL if available
    REGION="${GCP_REGION:-us-central1}"
    BACKEND_URL=$(gcloud run services describe knowledge-navigator-backend \
        --region "$REGION" \
        --format 'value(status.url)' 2>/dev/null || echo "")
    
    if [ -z "$BACKEND_URL" ]; then
        log_warn "Backend URL non trovato. Usa URL di default."
        BACKEND_URL="https://knowledge-navigator-backend-${REGION}-${GCP_PROJECT_ID}.a.run.app"
    fi
    
    log_info "Using backend URL: $BACKEND_URL"
    
    docker build \
        --platform linux/amd64 \
        -f Dockerfile.frontend \
        --build-arg NEXT_PUBLIC_API_URL="$BACKEND_URL" \
        -t gcr.io/${GCP_PROJECT_ID}/knowledge-navigator-frontend:latest .
    
    docker tag gcr.io/${GCP_PROJECT_ID}/knowledge-navigator-frontend:latest \
        gcr.io/${GCP_PROJECT_ID}/knowledge-navigator-frontend:$(date +%Y%m%d-%H%M%S)
    
    log_info "✅ Frontend image built"
}

function push_frontend() {
    log_info "Pushing frontend image to Google Container Registry..."
    docker push gcr.io/${GCP_PROJECT_ID}/knowledge-navigator-frontend:latest
    log_info "✅ Frontend image pushed"
}

function deploy_frontend() {
    log_info "Deploying frontend to Cloud Run..."
    
    REGION="${GCP_REGION:-us-central1}"
    BACKEND_URL=$(gcloud run services describe knowledge-navigator-backend \
        --region "$REGION" \
        --format 'value(status.url)')
    
    if [ -z "$BACKEND_URL" ]; then
        log_error "Backend non trovato. Deploy backend prima del frontend."
        exit 1
    fi
    
    gcloud run deploy knowledge-navigator-frontend \
        --image gcr.io/${GCP_PROJECT_ID}/knowledge-navigator-frontend:latest \
        --platform managed \
        --region "$REGION" \
        --allow-unauthenticated \
        --port 3000 \
        --memory 512Mi \
        --cpu 1 \
        --timeout 60 \
        --max-instances 5 \
        --set-env-vars "NEXT_PUBLIC_API_URL=${BACKEND_URL}"
    
    FRONTEND_URL=$(gcloud run services describe knowledge-navigator-frontend \
        --region "$REGION" \
        --format 'value(status.url)')
    
    log_info "✅ Frontend deployed: $FRONTEND_URL"
    echo "$FRONTEND_URL"
}

function main() {
    log_info "🚀 Starting Cloud Run deployment..."
    
    check_prerequisites
    check_syntax
    load_env_file
    check_gcp_project
    enable_apis
    configure_docker
    
    DEPLOY_TARGET="${1:-all}"
    REGION="${GCP_REGION:-us-central1}"
    
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
            BACKEND_URL=$(deploy_backend)
            log_info "Waiting for backend to be ready..."
            sleep 10
            build_frontend
            push_frontend
            FRONTEND_URL=$(deploy_frontend)
            ;;
        *)
            log_error "Usage: $0 [backend|frontend|all]"
            exit 1
            ;;
    esac
    
    log_info "🎉 Deployment completed!"
    log_info "Backend URL: $(gcloud run services describe knowledge-navigator-backend --region "$REGION" --format 'value(status.url)' 2>/dev/null || echo 'N/A')"
    log_info "Frontend URL: $(gcloud run services describe knowledge-navigator-frontend --region "$REGION" --format 'value(status.url)' 2>/dev/null || echo 'N/A')"
}

main "$@"

