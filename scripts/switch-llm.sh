#!/bin/bash

# Script to quickly switch LLM provider between Ollama and Gemini
# Usage: ./scripts/switch-llm.sh [ollama|gemini]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

LLM_PROVIDER="${1:-}"

cd "$PROJECT_ROOT"

ENV_FILE=".env"

if [ ! -f "$ENV_FILE" ]; then
    echo "❌ No .env file found!"
    exit 1
fi

# If no argument provided, show current status and toggle
if [ -z "$LLM_PROVIDER" ]; then
    CURRENT=$(grep "^LLM_PROVIDER=" "$ENV_FILE" | cut -d'=' -f2 || echo "unknown")
    echo "📋 Current LLM Provider: $CURRENT"
    echo ""
    if [ "$CURRENT" == "ollama" ]; then
        echo "💡 To switch to Gemini: ./scripts/switch-llm.sh gemini"
    elif [ "$CURRENT" == "gemini" ]; then
        echo "💡 To switch to Ollama: ./scripts/switch-llm.sh ollama"
    else
        echo "💡 Usage: ./scripts/switch-llm.sh [ollama|gemini]"
    fi
    exit 0
fi

if [ "$LLM_PROVIDER" != "ollama" ] && [ "$LLM_PROVIDER" != "gemini" ]; then
    echo "❌ Invalid LLM provider: $LLM_PROVIDER"
    echo "Usage: $0 [ollama|gemini]"
    exit 1
fi

# Get current provider
CURRENT=$(grep "^LLM_PROVIDER=" "$ENV_FILE" | cut -d'=' -f2 || echo "unknown")

if [ "$CURRENT" == "$LLM_PROVIDER" ]; then
    echo "✅ Already using $LLM_PROVIDER"
    exit 0
fi

# Backup .env
BACKUP_FILE=".env.backup.$(date +%Y%m%d_%H%M%S)"
cp "$ENV_FILE" "$BACKUP_FILE"
echo "📦 Backed up .env to $BACKUP_FILE"

# Update LLM_PROVIDER
if grep -q "^LLM_PROVIDER=" "$ENV_FILE"; then
    # Replace existing line
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/^LLM_PROVIDER=.*/LLM_PROVIDER=$LLM_PROVIDER/" "$ENV_FILE"
    else
        # Linux
        sed -i "s/^LLM_PROVIDER=.*/LLM_PROVIDER=$LLM_PROVIDER/" "$ENV_FILE"
    fi
else
    # Add new line
    echo "LLM_PROVIDER=$LLM_PROVIDER" >> "$ENV_FILE"
fi

echo "✅ Switched LLM provider: $CURRENT → $LLM_PROVIDER"

# Show configuration
echo ""
echo "📋 Configuration:"
if [ "$LLM_PROVIDER" == "gemini" ]; then
    GEMINI_KEY=$(grep "^GEMINI_API_KEY=" "$ENV_FILE" | cut -d'=' -f2 || echo "")
    if [ -z "$GEMINI_KEY" ] || [ "$GEMINI_KEY" == "your-gemini-api-key-here" ]; then
        echo "   ⚠️  Warning: GEMINI_API_KEY not configured!"
    else
        echo "   ✓ Gemini API key configured"
    fi
    GEMINI_MODEL=$(grep "^GEMINI_MODEL=" "$ENV_FILE" | cut -d'=' -f2 || echo "gemini-2.5-flash")
    echo "   Model: $GEMINI_MODEL"
elif [ "$LLM_PROVIDER" == "ollama" ]; then
    OLLAMA_URL=$(grep "^OLLAMA_BASE_URL=" "$ENV_FILE" | cut -d'=' -f2 || echo "http://localhost:11434")
    OLLAMA_MODEL=$(grep "^OLLAMA_MODEL=" "$ENV_FILE" | cut -d'=' -f2 || echo "gpt-oss:20b")
    echo "   URL: $OLLAMA_URL"
    echo "   Model: $OLLAMA_MODEL"
fi

echo ""
echo "💡 Next steps:"
echo "   1. Restart backend to apply changes"
echo "   2. Run: ./scripts/restart_backend.sh"
echo "   3. Or manually: cd backend && source venv/bin/activate && pkill -f uvicorn && python -m uvicorn app.main:app --reload"

