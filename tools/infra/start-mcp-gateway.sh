#!/bin/bash

# Start Docker MCP Gateway as a background service
echo "Starting Docker MCP Gateway as a background service..."

# Kill any existing MCP Gateway processes
pkill -f "docker mcp gateway run" 2>/dev/null

# Load environment variables from .env (project root) or backend/.env (legacy)
ENV_FILE=".env"
if [ ! -f "$ENV_FILE" ] && [ -f "backend/.env" ]; then
    ENV_FILE="backend/.env"
fi

if [ -f "$ENV_FILE" ]; then
    echo "Loading environment variables from $ENV_FILE..."
    # Load GOOGLE_MAPS_API_KEY
    export $(grep -v '^#' "$ENV_FILE" | grep GOOGLE_MAPS_API_KEY | xargs)
    # Load MCP_GATEWAY_AUTH_TOKEN (if present)
    if grep -q "MCP_GATEWAY_AUTH_TOKEN" "$ENV_FILE"; then
        export $(grep -v '^#' "$ENV_FILE" | grep MCP_GATEWAY_AUTH_TOKEN | xargs)
        echo "MCP_GATEWAY_AUTH_TOKEN loaded from $ENV_FILE"
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

# Wait a bit for the gateway to start
sleep 6

# Check if gateway is using existing token or generated a new one
echo "📋 Verificando configurazione token MCP Gateway..."

# Wait a bit more for logs to appear
sleep 2

# Check if gateway is using the token we passed
if tail -100 mcp-gateway.log | grep -q "Use Bearer token from MCP_GATEWAY_AUTH_TOKEN"; then
    echo "✅ Gateway sta usando il token passato come variabile d'ambiente"
    # Use the token we already have
    GENERATED_TOKEN="$MCP_GATEWAY_AUTH_TOKEN"
elif tail -100 mcp-gateway.log | grep -q "Use Bearer token:"; then
    # Gateway generated a new token - extract it from logs
    echo "📋 Estraendo il token generato dal gateway dai log..."
    GENERATED_TOKEN=$(tail -100 mcp-gateway.log | grep "Use Bearer token:" | tail -1 | sed -n 's/.*Bearer \([a-zA-Z0-9]*\).*/\1/p')
else
    echo "⚠️  Impossibile determinare il token dal gateway"
    GENERATED_TOKEN=""
fi

if [ -n "$GENERATED_TOKEN" ]; then
    echo "✅ Token generato dal gateway: ${GENERATED_TOKEN:0:30}..."
    
    # Determine which .env file to update (prefer project root .env)
    TARGET_ENV_FILE=".env"
    if [ ! -f "$TARGET_ENV_FILE" ] && [ -f "backend/.env" ]; then
        TARGET_ENV_FILE="backend/.env"
    fi
    
    echo "   Aggiornando $TARGET_ENV_FILE..."
    
    # Remove old MCP_GATEWAY_AUTH_TOKEN line if exists
    if [ -f "$TARGET_ENV_FILE" ]; then
        # Use appropriate sed command based on OS
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' '/^MCP_GATEWAY_AUTH_TOKEN=/d' "$TARGET_ENV_FILE"
        else
            sed -i '/^MCP_GATEWAY_AUTH_TOKEN=/d' "$TARGET_ENV_FILE"
        fi
    fi
    
    # Add new token to .env file
    echo "MCP_GATEWAY_AUTH_TOKEN=$GENERATED_TOKEN" >> "$TARGET_ENV_FILE"
    echo "✅ Token aggiornato nel $TARGET_ENV_FILE"
    echo ""
    echo "⚠️  IMPORTANTE: Il backend deve essere riavviato per usare il nuovo token!"
    echo "   Esegui: ./scripts/restart_backend.sh oppure riavvia manualmente il backend"
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
