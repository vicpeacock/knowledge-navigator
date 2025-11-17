#!/bin/bash
# Wrapper script che chiama scripts/stop.sh
# Questo script può essere sostituito con un link simbolico: ln -sf scripts/stop.sh stop.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec /bin/bash "$SCRIPT_DIR/scripts/stop.sh" "$@"

