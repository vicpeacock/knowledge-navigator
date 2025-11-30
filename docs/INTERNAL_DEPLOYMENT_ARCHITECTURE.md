# Architettura Deployment - Knowledge Navigator

## Panoramica

Knowledge Navigator è deployato su Google Cloud Run con supporto locale via Docker Compose.

---

## Cloud Run Deployment

### Backend Service
- **Platform**: Google Cloud Run
- **Runtime**: Python 3.11
- **Container**: Docker image in Artifact Registry
- **Scaling**: Automatico basato su richieste

### Database
- **PostgreSQL**: Supabase (cloud) o locale (Docker)
- **ChromaDB**: ChromaDB Cloud o locale (Docker)

### Storage
- **Files**: Google Cloud Storage
- **Backups**: Automatici per database

---

## Local Development

### Docker Compose
- PostgreSQL container
- ChromaDB container
- Backend (opzionale, può essere eseguito direttamente)

### Services
- Backend: FastAPI su porta 8000
- Frontend: Next.js su porta 3000
- PostgreSQL: porta 5432
- ChromaDB: porta 8001

---

## Configuration

### Environment Variables
- `.env` per configurazione locale
- Cloud Run environment variables per deployment

### Secrets Management
- Google Secret Manager per produzione
- `.env` file (gitignored) per sviluppo

---

## Riferimenti

- `docker-compose.yml` - Local setup
- `cloud-run/` - Cloud deployment scripts
- `Dockerfile.backend` - Backend container
