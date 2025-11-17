#!/bin/bash
# Wrapper che chiama lo script completo in tools/infra/
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$DIR/.." && pwd)"
exec "$PROJECT_ROOT/tools/infra/cleanup-playwright-containers.sh" "$@"

