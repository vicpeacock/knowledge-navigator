#!/bin/bash
# Script to run all backend tests

set -e

echo "🧪 Running all backend tests..."

cd "$(dirname "$0")/.."

# Check if pytest is available
if ! command -v pytest &> /dev/null; then
    echo "❌ pytest not found. Installing..."
    pip install pytest pytest-asyncio
fi

# Run all tests
echo "📋 Running test suite..."
pytest backend/tests/ -v --tb=short

echo "✅ All tests completed!"

