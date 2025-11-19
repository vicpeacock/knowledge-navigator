#!/bin/bash

# Script to switch between local and cloud environment configurations
# Usage: ./scripts/switch-env.sh [local|cloud]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

ENV_TYPE="${1:-local}"

if [ "$ENV_TYPE" != "local" ] && [ "$ENV_TYPE" != "cloud" ]; then
    echo "❌ Invalid environment type: $ENV_TYPE"
    echo "Usage: $0 [local|cloud]"
    exit 1
fi

ENV_FILE=".env.$ENV_TYPE"
TARGET_FILE=".env"

cd "$PROJECT_ROOT"

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Environment file not found: $ENV_FILE"
    echo "   Create it from the template first."
    exit 1
fi

# Backup existing .env if it exists
if [ -f "$TARGET_FILE" ]; then
    BACKUP_FILE=".env.backup.$(date +%Y%m%d_%H%M%S)"
    cp "$TARGET_FILE" "$BACKUP_FILE"
    echo "📦 Backed up existing .env to $BACKUP_FILE"
fi

# Copy environment file
cp "$ENV_FILE" "$TARGET_FILE"
echo "✅ Switched to $ENV_TYPE environment"
echo "   Active config: $ENV_FILE → $TARGET_FILE"

# Show current LLM provider
if [ -f "$TARGET_FILE" ]; then
    LLM_PROVIDER=$(grep "^LLM_PROVIDER=" "$TARGET_FILE" | cut -d'=' -f2 || echo "unknown")
    echo "   LLM Provider: $LLM_PROVIDER"
    
    if [ "$LLM_PROVIDER" == "gemini" ]; then
        GEMINI_KEY=$(grep "^GEMINI_API_KEY=" "$TARGET_FILE" | cut -d'=' -f2 || echo "")
        if [ -z "$GEMINI_KEY" ] || [ "$GEMINI_KEY" == "your-gemini-api-key-here" ]; then
            echo "   ⚠️  Warning: GEMINI_API_KEY not configured!"
        else
            echo "   ✓ Gemini API key configured"
        fi
    elif [ "$LLM_PROVIDER" == "ollama" ]; then
        echo "   ✓ Ollama configuration (local with Metal GPU)"
    fi
fi

echo ""
echo "💡 Next steps:"
if [ "$ENV_TYPE" == "local" ]; then
    echo "   1. Ensure Ollama is running: ollama serve"
    echo "   2. Ensure llama.cpp is running on port 11435"
    echo "   3. Restart backend: ./scripts/restart_backend.sh"
else
    echo "   1. Set GEMINI_API_KEY in .env.cloud"
    echo "   2. Configure database and ChromaDB URLs for cloud"
    echo "   3. Deploy to Cloud Run: ./cloud-run/deploy.sh"
fi

