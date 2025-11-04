#!/usr/bin/env python3
"""
Auto-versioning system per Knowledge Navigator
Salva automaticamente lo stato del progetto prima di modifiche importanti
"""
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import os

REPO_DIR = Path(__file__).parent

def run_git_command(cmd):
    """Esegue un comando git e restituisce il risultato"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=REPO_DIR
        )
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def has_changes():
    """Verifica se ci sono modifiche non committate"""
    success, _, _ = run_git_command("git diff --quiet && git diff --cached --quiet")
    return not success  # Se il comando fallisce, ci sono modifiche

def auto_commit(message="Auto-save"):
    """Fai commit automatico delle modifiche"""
    if not has_changes():
        print("ℹ️  No changes to commit")
        return True
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    full_message = f"Auto-save: {message}\n\nTimestamp: {timestamp}\nAuto-committed by auto_version.py"
    
    # Aggiungi tutti i file
    success, _, err = run_git_command("git add -A")
    if not success:
        print(f"❌ Error staging files: {err}")
        return False
    
    # Commit
    success, out, err = run_git_command(f'git commit -m "{full_message}"')
    if success:
        print(f"✅ Auto-committed: {message}")
        return True
    else:
        print(f"⚠️  Commit failed: {err}")
        return False

def create_snapshot(reason="Manual snapshot"):
    """Crea uno snapshot dello stato corrente"""
    snapshot_id = f"snapshot-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    # Commit modifiche correnti se presenti
    if has_changes():
        auto_commit(f"Snapshot before: {reason}")
    
    # Crea branch per snapshot
    success, _, err = run_git_command(f"git branch {snapshot_id}")
    if success:
        print(f"✅ Snapshot created: {snapshot_id}")
        print(f"   To restore: git checkout {snapshot_id}")
        return True
    else:
        print(f"❌ Failed to create snapshot: {err}")
        return False

def get_modified_files():
    """Ottiene lista dei file modificati"""
    success, out, _ = run_git_command("git diff --name-only")
    if success and out.strip():
        return out.strip().split('\n')
    return []

def before_modify_hook():
    """Hook da chiamare prima di modifiche importanti"""
    modified = get_modified_files()
    if modified:
        print(f"📝 Modified files detected: {len(modified)}")
        for f in modified[:5]:  # Mostra primi 5
            print(f"   - {f}")
        if len(modified) > 5:
            print(f"   ... and {len(modified) - 5} more")
        
        # Auto-commit
        auto_commit("Auto-save before modifications")
    else:
        print("✅ No uncommitted changes")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python auto_version.py {commit|snapshot|check} [message]")
        sys.exit(1)
    
    command = sys.argv[1]
    message = sys.argv[2] if len(sys.argv) > 2 else "Auto-save"
    
    if command == "commit":
        auto_commit(message)
    elif command == "snapshot":
        create_snapshot(message)
    elif command == "check":
        before_modify_hook()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

