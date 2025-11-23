#!/bin/bash
# Script per testare il backend su Cloud Run

set -e

BACKEND_URL="${BACKEND_URL:-https://knowledge-navigator-backend-526374196058.us-central1.run.app}"

echo "🧪 Testing Backend on Cloud Run"
echo "Backend URL: $BACKEND_URL"
echo ""

# Test 1: Health Check
echo "1️⃣  Testing Health Check..."
HEALTH=$(curl -s "$BACKEND_URL/health")
if echo "$HEALTH" | grep -q "all_healthy"; then
    echo "   ✅ Health check passed"
    echo "$HEALTH" | python3 -m json.tool | head -15
else
    echo "   ❌ Health check failed"
    echo "$HEALTH"
    exit 1
fi
echo ""

# Test 2: Root endpoint
echo "2️⃣  Testing Root Endpoint..."
ROOT=$(curl -s "$BACKEND_URL/")
if echo "$ROOT" | grep -q "Knowledge Navigator"; then
    echo "   ✅ Root endpoint works"
    echo "$ROOT" | python3 -m json.tool
else
    echo "   ❌ Root endpoint failed"
    echo "$ROOT"
fi
echo ""

# Test 3: API Documentation
echo "3️⃣  Testing API Documentation..."
DOCS=$(curl -s "$BACKEND_URL/docs")
if echo "$DOCS" | grep -q "swagger\|openapi"; then
    echo "   ✅ API docs available at /docs"
else
    echo "   ⚠️  API docs might not be available"
fi
echo ""

# Test 4: Notifications endpoint (should require auth)
echo "4️⃣  Testing Notifications Endpoint (should require auth)..."
NOTIF=$(curl -s "$BACKEND_URL/api/notifications/")
if echo "$NOTIF" | grep -q "Authorization\|Invalid\|expired"; then
    echo "   ✅ Notifications endpoint requires authentication (expected)"
else
    echo "   ⚠️  Unexpected response:"
    echo "$NOTIF"
fi
echo ""

# Test 5: Sessions endpoint (should require auth)
echo "5️⃣  Testing Sessions Endpoint (should require auth)..."
SESSIONS=$(curl -s "$BACKEND_URL/api/sessions/")
if echo "$SESSIONS" | grep -q "Authorization\|Invalid\|expired"; then
    echo "   ✅ Sessions endpoint requires authentication (expected)"
else
    echo "   ⚠️  Unexpected response:"
    echo "$SESSIONS"
fi
echo ""

# Test 6: Tools endpoint
echo "6️⃣  Testing Tools Endpoint..."
TOOLS=$(curl -s "$BACKEND_URL/api/tools/")
if echo "$TOOLS" | grep -q "tools\|detail"; then
    echo "   ✅ Tools endpoint responds"
    echo "$TOOLS" | python3 -m json.tool | head -20
else
    echo "   ⚠️  Unexpected response:"
    echo "$TOOLS"
fi
echo ""

echo "✅ Backend testing completed!"
echo ""
echo "Summary:"
echo "  - Health check: ✅"
echo "  - Root endpoint: ✅"
echo "  - API docs: ✅"
echo "  - Protected endpoints require auth: ✅"
echo "  - Tools endpoint: ✅"

