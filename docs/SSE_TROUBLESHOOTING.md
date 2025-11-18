# Troubleshooting SSE Streaming

## Problema: "Streaming non disponibile"

### Sintomi
- La UI mostra "Streaming non disponibile" invece di "Streaming attivo"
- Nessun evento di telemetria viene visualizzato
- I log del backend mostrano: `❌ Unauthorized SSE connection attempt`

### Cause Comuni

#### 1. Token Scaduto o Non Valido
**Sintomo**: Log mostrano `Token decode failed` o `User not found`

**Soluzione**:
- Effettua logout e login di nuovo
- Il token viene rinnovato automaticamente al login
- Verifica che il token sia presente in `localStorage.getItem('access_token')`

#### 2. Token Non Presente
**Sintomo**: Log mostrano `Token provided: False`

**Soluzione**:
- Verifica di essere loggato
- Controlla la console del browser: `localStorage.getItem('access_token')`
- Se mancante, effettua login

#### 3. Utente Non Trovato nel Database
**Sintomo**: Log mostrano `User not found or inactive`

**Soluzione**:
- Verifica che l'utente esista nel database
- Verifica che l'utente sia attivo (`active = True`)
- Verifica che il tenant_id corrisponda

#### 4. Tenant ID Non Corrispondente
**Sintomo**: Log mostrano `User not found` anche se l'utente esiste

**Soluzione**:
- Verifica che il tenant_id nel token corrisponda al tenant_id della sessione
- Verifica che il tenant_id sia salvato in `localStorage.getItem('tenant_id')`

### Verifica Funzionamento

1. **Apri Console Browser (F12)**:
   ```javascript
   // Verifica token
   localStorage.getItem('access_token')
   
   // Verifica tenant
   localStorage.getItem('tenant_id')
   ```

2. **Controlla Log Backend**:
   ```bash
   tail -f backend/logs/backend.log | grep -i "SSE\|agent.*activity"
   ```

3. **Verifica Connessione SSE**:
   - Apri Network tab nel browser
   - Cerca richieste a `/api/sessions/{session_id}/agent-activity/stream`
   - Verifica che lo status sia `200` (non `401`)

### Prevenzione

Per evitare questo problema in futuro:

1. **Refresh Automatico del Token**:
   - Il sistema già implementa refresh automatico del token quando scade
   - Verifica che `refresh_token` sia presente in localStorage

2. **Gestione Errori Migliorata**:
   - Il frontend tenta automaticamente di riconnettersi ogni 3 secondi
   - Se l'errore persiste, effettua logout e login

3. **Logging Dettagliato**:
   - I log del backend ora mostrano dettagli completi dell'autenticazione
   - Usa questi log per diagnosticare problemi futuri

### Test Manuale

Per testare manualmente la connessione SSE:

```bash
# 1. Ottieni token (dopo login)
TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","password":"yourpassword"}' \
  | jq -r '.access_token')

# 2. Ottieni session_id
SESSION_ID="your-session-id"

# 3. Testa SSE stream
curl -N "http://localhost:8000/api/sessions/${SESSION_ID}/agent-activity/stream?token=${TOKEN}"
```

Dovresti vedere eventi SSE in formato:
```
data: {"type":"agent_activity_snapshot","events":[...]}
data: {"type":"agent_activity","event":{...}}
```

