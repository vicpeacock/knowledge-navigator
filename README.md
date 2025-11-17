# Knowledge Navigator

Personal AI Assistant - Sistema multi-agente per gestione conoscenza e automazione.

## Quick Start

```bash
# Avvia tutti i servizi
./start.sh

# Ferma tutti i servizi
./stop.sh

# Riavvia solo il backend
./scripts/restart_backend.sh
```

## Struttura Progetto

- **`backend/`** - Backend FastAPI con agenti LangGraph
- **`frontend/`** - Frontend Next.js/React
- **`scripts/`** - Script di servizio (start, stop, restart, etc.)
- **`docs/`** - Documentazione del progetto
- **`tools/`** - Strumenti di sviluppo e infrastruttura

## Documentazione

Tutta la documentazione è in `docs/`:
- **`docs/SCRIPTS.md`** - Documentazione degli script
- **`docs/TROUBLESHOOTING_AUTH.md`** - Troubleshooting autenticazione
- **`docs/QUICK_FIX_AUTH.md`** - Quick fix problemi autenticazione
- **`docs/KAGGLE_SUBMISSION_ROADMAP.md`** - Roadmap challenge Kaggle
- E altri...

## Script Disponibili

Tutti gli script sono in `scripts/`:
- `start.sh` - Avvia tutti i servizi
- `stop.sh` - Ferma tutti i servizi
- `restart_backend.sh` - Riavvia solo il backend
- Altri script di utilità...

Vedi `docs/SCRIPTS.md` per la documentazione completa.

## Link Simbolici

Gli script `start.sh` e `stop.sh` nella root sono link simbolici a `scripts/start.sh` e `scripts/stop.sh` per comodità.
