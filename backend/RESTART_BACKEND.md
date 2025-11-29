# Riavvio Backend per Test

Il backend è stato fermato. Per riavviarlo:

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Oppure usa lo script:

```bash
cd "/Users/pallotta/Personal AI Assistant"
bash scripts/restart_backend.sh
```

Dopo il riavvio, esegui il test:

```bash
cd backend
python3 test_local_vertex_ai.py
```

## Cosa testare:

1. ✅ Health check funziona
2. ✅ Login funziona
3. ✅ Creazione sessione funziona
4. ✅ Chat semplice funziona (senza errori di system role)
5. ✅ Verifica nei log che non ci siano errori "Unable to submit request because a request can only contain one System role content"

## Log da controllare:

```bash
tail -f backend/logs/backend.log | grep -E "(system|System|ERROR|❌|Vertex AI)"
```

