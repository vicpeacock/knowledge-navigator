# Telemetria Sistema Proattività

## Problema Identificato

Il sistema di proattività (EventMonitor) girava in background ma **non emetteva eventi di telemetria**, quindi non appariva nella UI Agent Activity.

## Soluzione Implementata

### 1. Aggiunta Telemetria a EventMonitor

Il sistema di proattività ora emette eventi di telemetria quando:
- ✅ Inizia un check eventi
- ✅ Controlla integrazioni Gmail
- ✅ Controlla integrazioni Calendar
- ✅ Completa il check
- ✅ Rileva errori

### 2. Eventi Pubblicati

Gli eventi vengono pubblicati a **tutte le sessioni attive** usando `publish_to_all_active_sessions()` perché il sistema di proattività è globale, non legato a una sessione specifica.

**Agent ID**: `event_monitor`  
**Agent Name**: `Event Monitor`

### 3. Status degli Eventi

- **started**: Quando inizia un check
- **completed**: Quando completa un check (con o senza risultati)
- **error**: Quando c'è un errore

### 4. Messaggi Eventi

- `"Checking for new events"` - Check generale iniziato
- `"Checking Gmail integrations"` - Check email iniziato
- `"Found X new email(s)"` - Email trovate
- `"No new emails"` - Nessuna email nuova
- `"Checking Calendar integrations"` - Check calendar iniziato
- `"Found X upcoming event(s)"` - Eventi trovati
- `"No upcoming events"` - Nessun evento imminente
- `"Event check completed"` - Check completato

## Verifica Funzionamento

### 1. Apri una Sessione Chat

1. Vai su http://localhost:3003
2. Apri o crea una sessione chat
3. Apri il pannello **Agent Activity** (se disponibile)

### 2. Attendi il Polling

Ogni minuto (configurabile con `EVENT_MONITOR_POLL_INTERVAL_SECONDS`), dovresti vedere:

```
Event Monitor: started → "Checking for new events"
Event Monitor: started → "Checking Gmail integrations"
Event Monitor: completed → "No new emails" (o "Found X new email(s)")
Event Monitor: started → "Checking Calendar integrations"
Event Monitor: completed → "No upcoming events" (o "Found X upcoming event(s)")
Event Monitor: completed → "Event check completed"
```

### 3. Verifica nei Log

Nel terminale del backend, cerca:

```
INFO: Checking 1 Gmail integrations for new emails
INFO: Checking 1 Calendar integrations for upcoming events
📡📡📡 Publishing event to X subscriber(s) for session...
```

### 4. Verifica nella UI

Nel frontend, apri la console del browser (F12) e cerca:

```
[AgentActivity] Received SSE event: agent_activity event_monitor
[AgentActivity] Processing event: event_monitor started
```

## Troubleshooting

### Event Monitor non appare nella telemetria

1. **Verifica che Event Monitor sia abilitato:**
   ```bash
   # Nel .env
   EVENT_MONITOR_ENABLED=true
   ```

2. **Verifica che AgentActivityStream sia inizializzato:**
   ```bash
   # Nei log del backend all'avvio
   # Dovresti vedere: "✅ Event Monitor started"
   ```

3. **Verifica che ci siano sessioni attive:**
   - Apri una sessione chat nel frontend
   - Il frontend deve essere connesso alla SSE stream

4. **Verifica i log:**
   ```bash
   # Cerca nei log del backend
   grep "Publishing event" backend/logs/backend.log
   ```

### Eventi non arrivano al frontend

1. **Verifica connessione SSE:**
   - Apri console browser (F12)
   - Cerca: `[AgentActivity] SSE connection opened`

2. **Verifica URL SSE:**
   ```
   http://localhost:8000/api/sessions/{session_id}/agent-activity/stream
   ```

3. **Verifica autenticazione:**
   - Il token deve essere valido
   - Controlla header della richiesta SSE

### Eventi arrivano ma non vengono visualizzati

1. **Verifica che `event_monitor` sia in `AGENT_ORDER`:**
   ```typescript
   // frontend/components/AgentActivityContext.tsx
   const AGENT_ORDER = [
     ...
     'event_monitor',
   ]
   ```

2. **Verifica che `event_monitor` sia nel registry:**
   ```python
   # backend/app/agents/langgraph_app.py
   _AGENT_REGISTRY = {
       ...
       "event_monitor": "Event Monitor",
   }
   ```

## Test Manuale

Puoi triggerare manualmente un check per vedere gli eventi:

```bash
curl -X POST http://localhost:8000/api/notifications/check-events \
  -H "X-API-Key: your-api-key"
```

Dovresti vedere gli eventi di telemetria nel frontend entro pochi secondi.

## Prossimi Sviluppi

- [ ] Aggiungere telemetria anche ai singoli poller (EmailPoller, CalendarWatcher)
- [ ] Mostrare dettagli degli eventi trovati nella telemetria
- [ ] Aggiungere metriche per performance (tempo di check, numero eventi trovati)

