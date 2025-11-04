#!/bin/bash
# Auto-versioning script - Commits automaticamente le modifiche

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

# Colori per output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Funzione per fare commit automatico
auto_commit() {
    local message="$1"
    
    # Verifica se ci sono modifiche
    if git diff --quiet && git diff --cached --quiet; then
        echo -e "${YELLOW}No changes to commit${NC}"
        return
    fi
    
    # Aggiungi tutti i file modificati
    git add -A
    
    # Crea commit con timestamp
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    git commit -m "Auto-save: $message

Timestamp: $timestamp
Auto-committed by auto_version.sh" > /dev/null 2>&1
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Auto-committed: $message${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠ Commit failed (may be no changes)${NC}"
        return 1
    fi
}

# Funzione per creare snapshot prima di modifiche
create_snapshot() {
    local reason="$1"
    local snapshot_id="snapshot-$(date '+%Y%m%d-%H%M%S')"
    
    # Commit dello stato corrente
    if ! git diff --quiet || ! git diff --cached --quiet; then
        auto_commit "Snapshot before: $reason"
    fi
    
    # Crea branch per snapshot
    git branch "$snapshot_id" > /dev/null 2>&1
    echo -e "${GREEN}✓ Snapshot created: $snapshot_id${NC}"
    echo "  To restore: git checkout $snapshot_id"
}

# Funzione per monitorare i file in tempo reale
watch_files() {
    echo "Watching for file changes..."
    echo "Press Ctrl+C to stop"
    
    # Usa fswatch su macOS, inotifywait su Linux
    if command -v fswatch &> /dev/null; then
        fswatch -o . | while read f; do
            # Ignora file git e altri
            if [[ "$f" != *".git"* ]] && [[ "$f" != *"__pycache__"* ]] && [[ "$f" != *".pyc"* ]]; then
                auto_commit "File change detected"
            fi
        done
    elif command -v inotifywait &> /dev/null; then
        inotifywait -m -r -e modify,create,delete . | while read path action file; do
            if [[ "$path" != *".git"* ]] && [[ "$path" != *"__pycache__"* ]]; then
                auto_commit "File change: $action $file"
            fi
        done
    else
        echo "Error: fswatch (macOS) or inotifywait (Linux) not found"
        echo "Install with: brew install fswatch (macOS)"
        exit 1
    fi
}

# Menu principale
case "$1" in
    commit)
        auto_commit "${2:-Auto-save}"
        ;;
    snapshot)
        create_snapshot "${2:-Manual snapshot}"
        ;;
    watch)
        watch_files
        ;;
    *)
        echo "Usage: $0 {commit|snapshot|watch} [message]"
        echo ""
        echo "Commands:"
        echo "  commit [message]   - Commit automatico delle modifiche correnti"
        echo "  snapshot [reason]  - Crea snapshot prima di modifiche importanti"
        echo "  watch              - Monitora file e committa automaticamente"
        echo ""
        echo "Examples:"
        echo "  $0 commit 'Before editing memory_manager'"
        echo "  $0 snapshot 'Before major changes'"
        echo "  $0 watch"
        exit 1
        ;;
esac

