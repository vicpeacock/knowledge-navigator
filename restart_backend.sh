#!/bin/bash
cd "$(dirname "$0")/backend"

echo "Stopping backend..."
pkill -9 -f "uvicorn app.main:app"
sleep 2

echo "Token in .env:"
grep MCP_GATEWAY_AUTH_TOKEN .env || echo "NO TOKEN FOUND!"

echo ""
echo "Starting backend..."
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Test che il token sia caricabile
python3 -c "import sys; sys.path.insert(0, '.'); from app.core.config import settings; print(f'Token che verrà usato: {settings.mcp_gateway_auth_token[:30] if settings.mcp_gateway_auth_token else \"NONE\"}...')"

echo ""
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > backend.log 2>&1 &
echo "Backend started with PID: $!"

sleep 5
echo ""
echo "Checking if backend is responding..."
curl -s http://localhost:8000/docs > /dev/null && echo "✅ Backend is UP" || echo "❌ Backend is DOWN"
