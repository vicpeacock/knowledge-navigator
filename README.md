# Knowledge Navigator

Personal AI Assistant - Sistema multi-agente per gestione conoscenza e automazione.

## Quick Start

```bash
# Avvia tutti i servizi
./scripts/start.sh

# Ferma tutti i servizi
./scripts/stop.sh

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
- **`docs/ROADMAP.md`** - Roadmap generale del progetto
- **`docs/DAILY_SESSIONS_AND_NOTIFICATIONS.md`** - Sistema sessioni giornaliere e miglioramenti notifiche
- **`docs/SCRIPTS.md`** - Documentazione degli script
- **`docs/KAGGLE_SUBMISSION_ROADMAP.md`** - Roadmap challenge Kaggle
- **`docs/PROACTIVITY_ARCHITECTURE.md`** - Architettura sistema proattività
- E altri...

## Script Disponibili

Tutti gli script sono in `scripts/`:
- `start.sh` - Avvia tutti i servizi
- `stop.sh` - Ferma tutti i servizi
- `restart_backend.sh` - Riavvia solo il backend
- Altri script di utilità...

Vedi `docs/SCRIPTS.md` per la documentazione completa.

## Script di Servizio

Tutti gli script di servizio sono nella directory `scripts/`. Usa `./scripts/start.sh` e `./scripts/stop.sh` per avviare e fermare i servizi.
