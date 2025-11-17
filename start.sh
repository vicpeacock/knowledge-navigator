#!/bin/bash
# Wrapper script che chiama scripts/start.sh
# Questo script può essere sostituito con un link simbolico: ln -sf scripts/start.sh start.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec /bin/bash "$SCRIPT_DIR/scripts/start.sh" "$@"

