#!/bin/bash

# Script to check current environment configuration
# Usage: ./scripts/check-env.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

ENV_FILE=".env"

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ No .env file found!"
    echo "   Run: ./scripts/switch-env.sh [local|cloud]"
    exit 1
fi

echo "🔍 Checking environment configuration..."
echo ""

# Check LLM Provider
LLM_PROVIDER=$(grep "^LLM_PROVIDER=" "$ENV_FILE" | cut -d'=' -f2 || echo "unknown")
echo "📋 LLM Provider: $LLM_PROVIDER"

if [ "$LLM_PROVIDER" == "gemini" ]; then
    echo ""
    echo "🌐 Gemini Configuration:"
    GEMINI_MODEL=$(grep "^GEMINI_MODEL=" "$ENV_FILE" | cut -d'=' -f2 || echo "not set")
    echo "   Model: $GEMINI_MODEL"
    
    GEMINI_KEY=$(grep "^GEMINI_API_KEY=" "$ENV_FILE" | cut -d'=' -f2 || echo "")
    if [ -z "$GEMINI_KEY" ] || [ "$GEMINI_KEY" == "your-gemini-api-key-here" ]; then
        echo "   ⚠️  API Key: NOT CONFIGURED"
        echo "      Set GEMINI_API_KEY in $ENV_FILE"
    else
        # Show first 8 chars of key
        KEY_PREVIEW="${GEMINI_KEY:0:8}..."
        echo "   ✓ API Key: $KEY_PREVIEW (configured)"
    fi
    
    GEMINI_BG=$(grep "^GEMINI_BACKGROUND_MODEL=" "$ENV_FILE" | cut -d'=' -f2 || echo "")
    if [ -n "$GEMINI_BG" ]; then
        echo "   Background Model: $GEMINI_BG"
    fi
    
elif [ "$LLM_PROVIDER" == "ollama" ]; then
    echo ""
    echo "🤖 Ollama Configuration:"
    OLLAMA_URL=$(grep "^OLLAMA_BASE_URL=" "$ENV_FILE" | cut -d'=' -f2 || echo "not set")
    OLLAMA_MODEL=$(grep "^OLLAMA_MODEL=" "$ENV_FILE" | cut -d'=' -f2 || echo "not set")
    echo "   URL: $OLLAMA_URL"
    echo "   Model: $OLLAMA_MODEL"
    
    USE_LLAMA=$(grep "^USE_LLAMA_CPP_BACKGROUND=" "$ENV_FILE" | cut -d'=' -f2 || echo "false")
    if [ "$USE_LLAMA" == "true" ]; then
        LLAMA_URL=$(grep "^OLLAMA_BACKGROUND_BASE_URL=" "$ENV_FILE" | cut -d'=' -f2 || echo "not set")
        LLAMA_MODEL=$(grep "^OLLAMA_BACKGROUND_MODEL=" "$ENV_FILE" | cut -d'=' -f2 || echo "not set")
        echo "   Background: llama.cpp"
        echo "   llama.cpp URL: $LLAMA_URL"
        echo "   llama.cpp Model: $LLAMA_MODEL"
    else
        echo "   Background: Ollama"
    fi
    
    # Check if Ollama is running
    if curl -s "$OLLAMA_URL/api/tags" > /dev/null 2>&1; then
        echo "   ✓ Ollama is running"
    else
        echo "   ⚠️  Ollama is NOT running (expected: $OLLAMA_URL)"
    fi
else
    echo "   ⚠️  Unknown provider: $LLM_PROVIDER"
fi

echo ""
echo "🗄️  Database Configuration:"
DB_URL=$(grep "^DATABASE_URL=" "$ENV_FILE" | cut -d'=' -f2 || echo "not set")
if [[ "$DB_URL" == *"cloudsql"* ]] || [[ "$DB_URL" == *"run.app"* ]]; then
    echo "   Type: Cloud SQL"
elif [[ "$DB_URL" == *"localhost"* ]]; then
    echo "   Type: Local (Docker)"
else
    echo "   Type: External"
fi
echo "   URL: ${DB_URL:0:50}..." # Show first 50 chars

echo ""
echo "💾 ChromaDB Configuration:"
CHROMA_HOST=$(grep "^CHROMADB_HOST=" "$ENV_FILE" | cut -d'=' -f2 || echo "not set")
CHROMA_PORT=$(grep "^CHROMADB_PORT=" "$ENV_FILE" | cut -d'=' -f2 || echo "not set")
echo "   Host: $CHROMA_HOST"
echo "   Port: $CHROMA_PORT"

echo ""
echo "✅ Environment check complete!"
echo ""
echo "💡 To switch environments:"
echo "   ./scripts/switch-env.sh local   # Switch to local (Ollama)"
echo "   ./scripts/switch-env.sh cloud   # Switch to cloud (Gemini)"

