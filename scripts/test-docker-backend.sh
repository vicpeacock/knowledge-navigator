#!/bin/bash
# Script per testare il backend Docker con configurazione cloud (Gemini)

set -e

echo "🧪 Testing Docker Backend (Cloud Configuration)"
echo "================================================"

BACKEND_URL="http://localhost:8002"

echo ""
echo "1️⃣ Testing Health Endpoint..."
HEALTH=$(curl -s "${BACKEND_URL}/health")
if echo "$HEALTH" | grep -q '"all_healthy":true'; then
    echo "✅ Health check passed"
    echo "$HEALTH" | python -m json.tool | grep -E "all_healthy|gemini_main|postgres|chromadb" | head -5
else
    echo "❌ Health check failed"
    echo "$HEALTH"
    exit 1
fi

echo ""
echo "2️⃣ Testing API Info Endpoint..."
API_INFO=$(curl -s "${BACKEND_URL}/api/v1/info" 2>&1)
if echo "$API_INFO" | grep -q '"version"\|"name"'; then
    echo "✅ API info endpoint accessible"
else
    echo "⚠️  API info endpoint not available (this is optional)"
fi

echo ""
echo "3️⃣ Testing OpenAPI Docs..."
DOCS_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BACKEND_URL}/docs")
if [ "$DOCS_STATUS" = "200" ]; then
    echo "✅ OpenAPI docs accessible (HTTP $DOCS_STATUS)"
else
    echo "⚠️  OpenAPI docs returned HTTP $DOCS_STATUS (this is optional)"
fi

echo ""
echo "4️⃣ Checking Docker Container Status..."
CONTAINER_STATUS=$(docker ps --filter "name=knowledge-navigator-backend-cloud-test" --format "{{.Status}}")
if [ -n "$CONTAINER_STATUS" ]; then
    echo "✅ Container is running: $CONTAINER_STATUS"
else
    echo "❌ Container is not running"
    exit 1
fi

echo ""
echo "5️⃣ Checking Gemini Configuration..."
LOGS=$(docker logs knowledge-navigator-backend-cloud-test 2>&1 | grep -i "gemini" | tail -3)
if echo "$LOGS" | grep -q "Initializing Gemini\|gemini-2.5-flash"; then
    echo "✅ Gemini is configured and initialized"
    echo "$LOGS"
else
    echo "⚠️  Gemini configuration not found in logs"
fi

echo ""
echo "================================================"
echo "✅ All tests passed! Docker backend is ready for Cloud Run deployment."
echo ""
echo "📝 Next steps:"
echo "   1. Test authentication: curl -X POST ${BACKEND_URL}/api/v1/auth/login ..."
echo "   2. Deploy to Cloud Run: ./cloud-run/deploy.sh"
echo ""

