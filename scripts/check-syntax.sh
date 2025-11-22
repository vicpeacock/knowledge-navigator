#!/bin/bash
# Script to check Python syntax before committing

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "🔍 Checking Python syntax..."

# Find all Python files in backend/app
ERRORS=0
while IFS= read -r -d '' file; do
    if python3 -m py_compile "$file" 2>&1; then
        echo "  ✅ $(basename "$file")"
    else
        echo "  ❌ $(basename "$file") - Syntax error!"
        ERRORS=$((ERRORS + 1))
    fi
done < <(find backend/app -name "*.py" -type f -print0)

if [ $ERRORS -eq 0 ]; then
    echo "✅ All Python files have valid syntax"
    exit 0
else
    echo "❌ Found $ERRORS file(s) with syntax errors"
    exit 1
fi

