# Database Migrations Fix per Cloud Run

## Problema

Il backend su Cloud Run falliva con l'errore:
```
asyncpg.exceptions.UndefinedTableError: relation "notifications" does not exist
```

## Soluzione Implementata

Aggiunta esecuzione automatica delle migrations all'avvio del backend in `backend/app/main.py`:

```python
# Run database migrations (for Cloud Run deployment)
logging.info("🔄 Running database migrations...")
try:
    # Use subprocess to run alembic upgrade (most reliable method)
    import subprocess
    import sys
    from pathlib import Path
    
    # Change to backend directory where alembic.ini is located
    backend_dir = Path(__file__).parent.parent
    original_cwd = Path.cwd()
    
    try:
        os.chdir(backend_dir)
        
        # Run alembic upgrade
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            env={**os.environ, "DATABASE_URL": settings.database_url},
            capture_output=True,
            text=True,
            timeout=120,
            check=False
        )
        
        if result.returncode == 0:
            logging.info("✅ Database migrations completed")
        else:
            logging.error(f"❌ Migration failed with code {result.returncode}")
    finally:
        os.chdir(original_cwd)
except Exception as e:
    logging.error(f"❌ Failed to run database migrations: {e}", exc_info=True)
```

## Modifiche al Dockerfile

Aggiunto copia di `alembic.ini` nella root del container per accesso diretto:

```dockerfile
COPY backend/alembic.ini ./alembic.ini
```

## Verifica

Per verificare che le migrations siano state eseguite, controllare i log di Cloud Run:

```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=knowledge-navigator-backend AND textPayload=~'migration'" --limit=20 --project=knowledge-navigator-477022
```

## Note

- Le migrations vengono eseguite ad ogni avvio del container
- Se le migrations falliscono, il backend continua ad avviarsi (non blocca il startup)
- Le migrations sono idempotenti (possono essere eseguite multiple volte senza problemi)

