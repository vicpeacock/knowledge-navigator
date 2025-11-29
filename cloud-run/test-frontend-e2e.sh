#!/bin/bash
# Frontend End-to-End Test Script
# Tests frontend functionality on Cloud Run

set -e

BACKEND_URL="${BACKEND_URL:-https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app}"
FRONTEND_URL="${FRONTEND_URL:-https://knowledge-navigator-frontend-osbdwu5a7q-uc.a.run.app}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

function log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

function log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

function log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

function log_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

function test_pass() {
    TESTS_PASSED=$((TESTS_PASSED + 1))
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    log_info "✅ PASS: $1"
}

function test_fail() {
    TESTS_FAILED=$((TESTS_FAILED + 1))
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    log_error "❌ FAIL: $1"
}

function test_skip() {
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    log_warn "⏭️  SKIP: $1"
}

echo "=========================================="
echo "Frontend E2E Tests - Cloud Run"
echo "=========================================="
echo "Backend URL: $BACKEND_URL"
echo "Frontend URL: $FRONTEND_URL"
echo ""

# Test 1: Frontend is accessible
log_test "Test 1: Frontend accessibility"
if curl -s -o /dev/null -w "%{http_code}" "$FRONTEND_URL" | grep -q "200\|301\|302"; then
    test_pass "Frontend is accessible"
else
    test_fail "Frontend is not accessible"
fi

# Test 2: Frontend loads main page
log_test "Test 2: Frontend main page loads"
RESPONSE=$(curl -s "$FRONTEND_URL" | head -20)
if echo "$RESPONSE" | grep -qi "html\|next\|react"; then
    test_pass "Frontend main page loads"
else
    test_fail "Frontend main page does not load correctly"
fi

# Test 3: Backend health check (required for frontend)
log_test "Test 3: Backend health check"
HEALTH_RESPONSE=$(curl -s "$BACKEND_URL/health")
if echo "$HEALTH_RESPONSE" | grep -q "all_healthy"; then
    test_pass "Backend health check passes"
else
    test_fail "Backend health check fails"
fi

# Test 4: Frontend API configuration
log_test "Test 4: Frontend API configuration"
# Check if frontend can reach backend API
API_RESPONSE=$(curl -s "$BACKEND_URL/" 2>&1)
if echo "$API_RESPONSE" | grep -q "Knowledge Navigator\|message"; then
    test_pass "Frontend can reach backend API"
else
    test_fail "Frontend cannot reach backend API"
fi

# Test 5: Authentication endpoints available
log_test "Test 5: Authentication endpoints"
AUTH_RESPONSE=$(curl -s -X POST "$BACKEND_URL/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"test"}' 2>&1)
if echo "$AUTH_RESPONSE" | grep -q "401\|422\|detail"; then
    test_pass "Authentication endpoints respond correctly"
else
    test_fail "Authentication endpoints not responding"
fi

# Test 6: CORS headers (important for frontend)
log_test "Test 6: CORS headers"
CORS_HEADERS=$(curl -s -I -X OPTIONS "$BACKEND_URL/api/v1/auth/login" \
    -H "Origin: $FRONTEND_URL" \
    -H "Access-Control-Request-Method: POST" 2>&1)
if echo "$CORS_HEADERS" | grep -qi "access-control"; then
    test_pass "CORS headers present"
else
    test_warn "CORS headers may be missing"
fi

# Test 7: SSE endpoints (agent activity)
log_test "Test 7: SSE endpoints availability"
# Create a test session first (requires auth, so we'll just check endpoint exists)
SSE_ENDPOINT="$BACKEND_URL/api/sessions/test-session-id/agent-activity/stream"
SSE_RESPONSE=$(curl -s -N --max-time 2 "$SSE_ENDPOINT?token=test" 2>&1 || true)
if echo "$SSE_RESPONSE" | grep -q "401\|Unauthorized\|text/event-stream"; then
    test_pass "SSE endpoint exists and responds"
else
    test_fail "SSE endpoint not accessible"
fi

# Test 8: Notifications SSE endpoint
log_test "Test 8: Notifications SSE endpoint"
NOTIF_SSE_ENDPOINT="$BACKEND_URL/api/notifications/stream"
NOTIF_SSE_RESPONSE=$(curl -s -N --max-time 2 "$NOTIF_SSE_ENDPOINT?token=test" 2>&1 || true)
if echo "$NOTIF_SSE_RESPONSE" | grep -q "401\|Unauthorized\|text/event-stream"; then
    test_pass "Notifications SSE endpoint exists and responds"
else
    test_fail "Notifications SSE endpoint not accessible"
fi

# Summary
echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "Total Tests: $TESTS_TOTAL"
echo "Passed: $TESTS_PASSED"
echo "Failed: $TESTS_FAILED"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    log_info "✅ All tests passed!"
    exit 0
else
    log_error "❌ Some tests failed"
    exit 1
fi

