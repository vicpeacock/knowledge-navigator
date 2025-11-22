# Quick Start - Backend

## Avvio Backend

### Metodo 1: Script automatico (consigliato)
```bash
cd /Users/pallotta/Personal\ AI\ Assistant
bash tools/infra/start.sh
```

### Metodo 2: Manuale
```bash
cd backend

# Attiva virtual environment
source venv/bin/activate

# Avvia backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Metodo 3: In background
```bash
cd backend
source venv/bin/activate
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > backend.log 2>&1 &
```

## Verifica Backend

```bash
# Controlla se è in esecuzione
curl http://localhost:8000/health

# Controlla i log
tail -f backend/backend.log
```

## Risoluzione Problemi

### Porta 8000 già in uso
```bash
# Termina processi sulla porta 8000
lsof -ti:8000 | xargs kill -9
```

### Errori di import
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
```

### Database non disponibile
```bash
# Avvia Docker Compose
docker-compose up -d
```

