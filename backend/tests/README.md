# Test Suite - Knowledge Navigator Phase 1

Questa directory contiene le suite di test per completare la Fase 1 del progetto Knowledge Navigator.

## Test Disponibili

### 1. `test_email_indexer.py`
Test per il servizio di indicizzazione email in memoria long-term.

**Copertura:**
- Determinazione importanza email
- Indicizzazione email singole e multiple
- Gestione errori
- Calcolo score di importanza
- Costruzione contenuto email

**Eseguire:**
```bash
pytest tests/test_email_indexer.py -v
```

### 2. `test_web_indexer.py`
Test per il servizio di indicizzazione contenuti web.

**Copertura:**
- Estrazione testo da browser snapshots
- Indicizzazione risultati web search
- Indicizzazione risultati web fetch
- Indicizzazione browser snapshots
- Gestione errori e limiti

**Eseguire:**
```bash
pytest tests/test_web_indexer.py -v
```

### 3. `test_whatsapp_integration.py`
Test per l'integrazione WhatsApp.

**Copertura:**
- Inizializzazione servizio WhatsApp
- Setup e autenticazione
- Recupero messaggi
- Invio messaggi
- Endpoint API
- Gestione errori

**Eseguire:**
```bash
pytest tests/test_whatsapp_integration.py -v
```

## Installazione Dipendenze

```bash
pip install -r requirements.txt
```

## Eseguire Tutti i Test

```bash
# Dalla root del progetto
cd backend
pytest tests/ -v

# Con coverage
pytest tests/ --cov=app --cov-report=html
```

## Configurazione

I test utilizzano un database SQLite in-memory per isolamento e velocità. La configurazione è in `conftest.py`.

## Note

- I test per WhatsApp richiedono mocking completo di Selenium/Playwright
- I test per email e web indexing possono essere eseguiti senza dipendenze esterne
- Tutti i test sono asincroni e utilizzano `pytest-asyncio`

