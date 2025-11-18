# End-to-End Testing Guide

## Differenza tra Unit Test e E2E Test

### Unit Test (test_proactivity.py)
- **Scopo**: Testare componenti isolati
- **Database**: Mock (fittizio)
- **Servizi esterni**: Mock (Gmail, Calendar API)
- **Velocità**: Molto veloce (~0.5s per 28 test)
- **Quando usare**: Durante sviluppo, per verificare logica

### E2E Test (test_proactivity_e2e.py)
- **Scopo**: Testare il flusso completo
- **Database**: Reale (PostgreSQL o SQLite)
- **Servizi esterni**: Mock (per evitare chiamate reali)
- **Velocità**: Più lento (~2-5s per test)
- **Quando usare**: Prima del deploy, per verificare integrazione

## Setup per E2E Test

### Opzione 1: PostgreSQL via Docker (Consigliato)

PostgreSQL è già configurato in `docker-compose.yml`. I modelli usano tipi PostgreSQL-specifici (JSONB), quindi PostgreSQL è necessario.

```bash
# 1. Avvia PostgreSQL (se non è già in esecuzione)
docker-compose up -d postgres

# 2. Crea database di test (usa lo stesso PostgreSQL del progetto)
docker-compose exec postgres psql -U knavigator -c "CREATE DATABASE knowledge_navigator_test;"

# Oppure da host (se hai psql installato):
# PGPASSWORD=knavigator_pass createdb -h localhost -U knavigator knowledge_navigator_test

# 3. Esegui test (usa già la configurazione di default)
cd backend
source venv/bin/activate
pytest tests/test_proactivity_e2e.py -v

# I test usano automaticamente:
# postgresql+asyncpg://knavigator:knavigator_pass@localhost:5432/knowledge_navigator_test
```

### Opzione 2: SQLite (Limitato)

SQLite non supporta JSONB, quindi alcuni test potrebbero fallire. Per test semplificati:

```bash
# Usa SQLite in-memory (già configurato nei test)
pytest tests/test_proactivity_e2e.py -v
```

**Nota**: Alcuni test potrebbero fallire perché SQLite non supporta tutti i tipi PostgreSQL.

## Struttura Test E2E

### 1. Setup Database Reale

```python
@pytest_asyncio.fixture(scope="function")
async def test_db():
    """Create real database session"""
    engine = create_async_engine(TEST_DATABASE_URL)
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    session = AsyncSession(engine)
    yield session
    await session.rollback()
    # Cleanup
    await engine.dispose()
```

### 2. Creare Dati di Test

```python
@pytest_asyncio.fixture
async def test_integration(test_db):
    """Create test integration"""
    integration = Integration(...)
    test_db.add(integration)
    await test_db.commit()
    return integration
```

### 3. Mock Servizi Esterni

```python
with patch('app.services.email_poller.EmailService') as mock_service:
    mock_service.return_value.get_gmail_messages = AsyncMock(
        return_value=[{"id": "msg1", ...}]
    )
    # Esegui test con servizi mockati
```

### 4. Verificare Risultati nel Database

```python
# Verifica che le notifiche siano state create
result = await test_db.execute(
    select(Notification).where(Notification.type == "email_received")
)
notifications = result.scalars().all()
assert len(notifications) > 0
```

## Test E2E Implementati

### TestEmailPollerE2E
- ✅ `test_email_poller_creates_notifications` - Verifica creazione notifiche
- ✅ `test_email_poller_filters_duplicates` - Verifica filtro duplicati

### TestCalendarWatcherE2E
- ✅ `test_calendar_watcher_creates_notifications` - Verifica creazione notifiche calendar

### TestEventMonitorE2E
- ✅ `test_event_monitor_check_once` - Verifica orchestratore
- ✅ `test_event_monitor_with_disabled_components` - Verifica componenti disabilitati

### TestProactivityIntegrationE2E
- ✅ `test_full_proactivity_flow` - Test flusso completo

## Eseguire i Test

### Setup Iniziale (solo la prima volta)

```bash
# Crea il database di test usando lo script helper
./backend/scripts/setup_test_db.sh

# Oppure manualmente:
docker-compose exec postgres psql -U knavigator -c "CREATE DATABASE knowledge_navigator_test;"
```

### Solo Unit Test (veloce, senza database)
```bash
cd backend
source venv/bin/activate
pytest tests/test_proactivity.py -v
```

### Solo E2E Test (richiede PostgreSQL)
```bash
cd backend
source venv/bin/activate
pytest tests/test_proactivity_e2e.py -v
```

### Tutti i Test
```bash
cd backend
source venv/bin/activate
pytest tests/test_proactivity*.py -v
```

## Best Practices

1. **Isolamento**: Ogni test usa il proprio database/transazione
2. **Cleanup**: Sempre pulire dopo ogni test
3. **Mock esterni**: Mockare sempre API esterne (Gmail, Calendar)
4. **Dati realistici**: Usare dati di test realistici
5. **Verifica completa**: Verificare sia il risultato che lo stato del database

## Troubleshooting

### Errore: "JSONB not supported"
- **Causa**: SQLite non supporta JSONB
- **Soluzione**: Usa PostgreSQL per test E2E

### Errore: "async_generator object has no attribute 'execute'"
- **Causa**: Fixture async non gestita correttamente
- **Soluzione**: Usa `@pytest_asyncio.fixture` invece di `@pytest.fixture`

### Errore: "Table already exists"
- **Causa**: Database non pulito tra test
- **Soluzione**: Assicurati che ogni test faccia cleanup

## Prossimi Sviluppi

- [ ] Test E2E con PostgreSQL reale
- [ ] Test E2E con servizi esterni reali (opzionale)
- [ ] Test di performance E2E
- [ ] Test di carico E2E

