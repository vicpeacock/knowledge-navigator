#!/bin/bash
# Script per testare il deployment completo (backend + frontend) in Docker

set -e

echo "🧪 Testing Full Docker Deployment (Backend + Frontend)"
echo "========================================================"

BACKEND_URL="http://localhost:8002"
FRONTEND_URL="http://localhost:3004"

echo ""
echo "1️⃣ Testing Backend Health..."
BACKEND_HEALTH=$(curl -s "${BACKEND_URL}/health")
if echo "$BACKEND_HEALTH" | grep -q '"all_healthy":true'; then
    echo "✅ Backend health check passed"
    echo "$BACKEND_HEALTH" | python -m json.tool | grep -E "all_healthy|gemini_main|postgres|chromadb" | head -5
else
    echo "❌ Backend health check failed"
    echo "$BACKEND_HEALTH"
    exit 1
fi

echo ""
echo "2️⃣ Testing Frontend Accessibility..."
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${FRONTEND_URL}")
if [ "$FRONTEND_STATUS" = "200" ]; then
    echo "✅ Frontend is accessible (HTTP $FRONTEND_STATUS)"
else
    echo "❌ Frontend returned HTTP $FRONTEND_STATUS"
    exit 1
fi

echo ""
echo "3️⃣ Checking Docker Containers..."
BACKEND_CONTAINER=$(docker ps --filter "name=knowledge-navigator-backend-cloud-test" --format "{{.Status}}")
FRONTEND_CONTAINER=$(docker ps --filter "name=knowledge-navigator-frontend-cloud-test" --format "{{.Status}}")

if [ -n "$BACKEND_CONTAINER" ]; then
    echo "✅ Backend container: $BACKEND_CONTAINER"
else
    echo "❌ Backend container is not running"
    exit 1
fi

if [ -n "$FRONTEND_CONTAINER" ]; then
    echo "✅ Frontend container: $FRONTEND_CONTAINER"
else
    echo "❌ Frontend container is not running"
    exit 1
fi

echo ""
echo "4️⃣ Testing Frontend-Backend Connection..."
# Verifica che il frontend possa raggiungere il backend
FRONTEND_HTML=$(curl -s "${FRONTEND_URL}")
if echo "$FRONTEND_HTML" | grep -q "Knowledge Navigator"; then
    echo "✅ Frontend HTML loaded correctly"
else
    echo "⚠️  Frontend HTML might not be loading correctly"
fi

# Verifica che NEXT_PUBLIC_API_URL sia configurato
if echo "$FRONTEND_HTML" | grep -q "localhost:8002\|localhost:8000"; then
    echo "✅ Frontend is configured to connect to backend"
else
    echo "⚠️  Frontend API URL might not be configured correctly"
fi

echo ""
echo "5️⃣ Checking Gemini Configuration..."
BACKEND_LOGS=$(docker logs knowledge-navigator-backend-cloud-test 2>&1 | grep -i "gemini" | tail -3)
if echo "$BACKEND_LOGS" | grep -q "Initializing Gemini\|gemini-2.5-flash"; then
    echo "✅ Gemini is configured and initialized"
else
    echo "⚠️  Gemini configuration not found in logs"
fi

echo ""
echo "========================================================"
echo "✅ All tests passed! Full Docker deployment is ready."
echo ""
echo "📝 Access URLs:"
echo "   Frontend: ${FRONTEND_URL}"
echo "   Backend API: ${BACKEND_URL}"
echo "   Backend Docs: ${BACKEND_URL}/docs"
echo ""
echo "📝 Next steps:"
echo "   1. Open ${FRONTEND_URL} in your browser"
echo "   2. Test authentication and features"
echo "   3. Deploy to Cloud Run: ./cloud-run/deploy.sh all"
echo ""

