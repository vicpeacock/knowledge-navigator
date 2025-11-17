#!/bin/bash

# Start Docker MCP Gateway as a background service
echo "Starting Docker MCP Gateway as a background service..."

# Kill any existing MCP Gateway processes
pkill -f "docker mcp gateway run" 2>/dev/null

# Load environment variables from backend/.env if it exists
if [ -f "backend/.env" ]; then
    echo "Loading environment variables from backend/.env..."
    # Load GOOGLE_MAPS_API_KEY
    export $(grep -v '^#' backend/.env | grep GOOGLE_MAPS_API_KEY | xargs)
    # Load MCP_GATEWAY_AUTH_TOKEN (if present)
    if grep -q "MCP_GATEWAY_AUTH_TOKEN" backend/.env; then
        export $(grep -v '^#' backend/.env | grep MCP_GATEWAY_AUTH_TOKEN | xargs)
        echo "MCP_GATEWAY_AUTH_TOKEN loaded from backend/.env"
    fi
fi

# Start the MCP Gateway in the background
# Pass environment variables (GOOGLE_MAPS_API_KEY and MCP_GATEWAY_AUTH_TOKEN) to the gateway
ENV_VARS=""
if [ -n "$GOOGLE_MAPS_API_KEY" ]; then
    ENV_VARS="GOOGLE_MAPS_API_KEY=\"$GOOGLE_MAPS_API_KEY\""
    echo "GOOGLE_MAPS_API_KEY found, passing to MCP Gateway..."
else
    echo "⚠️  WARNING: GOOGLE_MAPS_API_KEY not set. Google Maps tools may not work."
fi

if [ -n "$MCP_GATEWAY_AUTH_TOKEN" ]; then
    if [ -n "$ENV_VARS" ]; then
        ENV_VARS="$ENV_VARS MCP_GATEWAY_AUTH_TOKEN=\"$MCP_GATEWAY_AUTH_TOKEN\""
    else
        ENV_VARS="MCP_GATEWAY_AUTH_TOKEN=\"$MCP_GATEWAY_AUTH_TOKEN\""
    fi
    echo "MCP_GATEWAY_AUTH_TOKEN found, passing to MCP Gateway..."
fi

if [ -n "$ENV_VARS" ]; then
    # Use eval to properly expand environment variables
    eval "nohup env $ENV_VARS docker mcp gateway run --port 8080 --transport streaming > mcp-gateway.log 2>&1 &"
else
    nohup docker mcp gateway run --port 8080 --transport streaming > mcp-gateway.log 2>&1 &
fi

# Get the process ID
PID=$!

# Save the PID to a file for later reference
echo $PID > mcp-gateway.pid

# Wait a bit for the gateway to start and generate token
sleep 6

# IMPORTANTE: Il gateway Docker MCP genera SEMPRE un nuovo token, anche se passiamo MCP_GATEWAY_AUTH_TOKEN
# Dobbiamo estrarre il token generato dai log e usarlo nel backend
echo "📋 Estraendo il token generato dal gateway dai log..."

# Wait a bit more for the token to appear in logs
sleep 2

# Extract token from logs - il gateway genera sempre un token e lo mostra nei log
GENERATED_TOKEN=$(tail -100 mcp-gateway.log | grep "Use Bearer token:" | tail -1 | sed -n 's/.*Bearer \([a-zA-Z0-9]*\).*/\1/p')

if [ -n "$GENERATED_TOKEN" ]; then
    echo "✅ Token generato dal gateway: ${GENERATED_TOKEN:0:30}..."
    echo "   Aggiornando backend/.env..."
    
    # Remove old MCP_GATEWAY_AUTH_TOKEN line if exists
    if [ -f "backend/.env" ]; then
        sed -i '' '/^MCP_GATEWAY_AUTH_TOKEN=/d' backend/.env
    fi
    
    # Add new token to backend/.env
    echo "MCP_GATEWAY_AUTH_TOKEN=$GENERATED_TOKEN" >> backend/.env
    echo "✅ Token aggiornato nel backend/.env"
    echo ""
    echo "⚠️  IMPORTANTE: Il backend deve essere riavviato per usare il nuovo token!"
    echo "   Esegui: ./restart_backend.sh (se disponibile) oppure:"
    echo "   cd backend && pkill -f uvicorn && sleep 2 && nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > backend.log 2>&1 &"
else
    echo "⚠️  Impossibile estrarre il token dai log. Controlla manualmente mcp-gateway.log"
    echo "   Cerca la riga: 'Use Bearer token: Authorization: Bearer <token>'"
fi

echo "Docker MCP Gateway started with PID: $PID"
echo "Logs are being written to: mcp-gateway.log"
echo "PID saved to: mcp-gateway.pid"
echo ""
echo "To stop the service, run: ./stop-mcp-gateway.sh"
echo "To view logs, run: tail -f mcp-gateway.log"
