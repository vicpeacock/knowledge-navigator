# Diagnosi Errore Tool MCP

## Problema

Il frontend mostra che OAuth è autorizzato, ma quando viene chiamato un tool MCP (es. `mcp_list_calendars`) c'è un errore.

## Possibili Cause

### 1. Token OAuth Scaduto

**Sintomi**:
- Frontend mostra "autorizzato"
- Tool chiamato fallisce con errore OAuth

**Verifica**:
```bash
# Controlla logs backend per vedere se il token viene recuperato
gcloud run services logs read knowledge-navigator-backend \
  --region us-central1 \
  --limit 50 | grep -i "oauth\|token\|retrieved"
```

**Soluzione**:
- Il sistema dovrebbe fare refresh automatico del token
- Se il refresh fallisce, riautentica OAuth:
  - Profile → Google Workspace MCP → "Revoke OAuth"
  - Poi "Authorize OAuth" di nuovo

### 2. Token Non Passato al Client MCP

**Sintomi**:
- Token recuperato correttamente
- Ma client MCP non lo riceve

**Verifica**:
Cerca nei logs:
```
✅ Retrieved OAuth token with refresh capability
Created MCP client with OAuth token
```

**Soluzione**:
- Verifica che `oauth_token` sia passato a `_get_mcp_client_for_integration`
- Verifica che `client.oauth_token` sia impostato correttamente

### 3. URL Server MCP Errato

**Sintomi**:
- HTTP 404 o "Endpoint non trovato"
- URL non include `/mcp` correttamente

**Verifica**:
```sql
SELECT session_metadata->>'server_url' 
FROM integrations 
WHERE service_type = 'mcp_server';
```

Dovrebbe essere: `https://google-workspace-mcp-osbdwu5a7q-uc.a.run.app`  
Il client aggiunge automaticamente `/mcp` alla fine.

**Soluzione**:
- Verifica che l'URL sia corretto nel database
- Non includere `/mcp` nell'URL salvato (viene aggiunto automaticamente)

### 4. Token Non Valido per Server MCP

**Sintomi**:
- Token recuperato correttamente
- Ma server MCP lo rifiuta (401/403)

**Verifica**:
Cerca nei logs:
```
HTTP 401 Unauthorized
Invalid token
```

**Soluzione**:
- Riautentica OAuth per ottenere un token fresco
- Verifica che gli scope OAuth siano corretti

### 5. Problema con Refresh Token

**Sintomi**:
- Token scaduto
- Refresh fallisce

**Verifica**:
Cerca nei logs:
```
Token refresh failed
No refresh token available
```

**Soluzione**:
- Riautentica OAuth (il refresh token potrebbe essere scaduto o revocato)
- Verifica che `refresh_token` sia salvato nelle credentials

## Debug Step-by-Step

### Step 1: Verifica Integrazione nel Database

```sql
SELECT 
    id,
    user_id,
    enabled,
    session_metadata->>'server_url' as server_url,
    jsonb_object_keys(session_metadata->'oauth_credentials') as oauth_user_ids
FROM integrations
WHERE service_type = 'mcp_server'
AND enabled = true;
```

### Step 2: Verifica OAuth Credentials

```sql
SELECT 
    session_metadata->'oauth_credentials'->'USER_ID_QUI' as oauth_creds
FROM integrations
WHERE service_type = 'mcp_server'
AND id = 'INTEGRATION_ID_QUI';
```

### Step 3: Test Tool Direttamente

Usa lo script `test-mcp-tool-direct.py`:

```bash
cd backend
source venv/bin/activate
python ../cloud-run/test-mcp-tool-direct.py
```

Lo script:
1. Trova l'integrazione MCP per l'utente
2. Recupera il token OAuth (con refresh)
3. Crea il client MCP
4. Testa `list_tools()`
5. Testa `call_tool('list_calendars')`

### Step 4: Verifica Logs Backend

```bash
# Logs recenti per tool calls
gcloud run services logs read knowledge-navigator-backend \
  --region us-central1 \
  --limit 100 | grep -A 10 "call_tool\|mcp_list_calendars\|Error calling tool"
```

Cerca:
- `✅ Retrieved OAuth token` → Token recuperato
- `Created MCP client with OAuth token` → Client creato con token
- `Error calling tool` → Errore specifico
- `HTTP 401` o `HTTP 403` → Problema autenticazione
- `HTTP 404` → URL errato
- `HTTP 406` → Header mancanti

## Soluzioni Rapide

### Soluzione 1: Riautentica OAuth

1. Vai a Profile → Google Workspace MCP
2. Clicca "Revoke OAuth"
3. Clicca "Authorize OAuth"
4. Completa il flusso OAuth
5. Prova di nuovo il tool

### Soluzione 2: Verifica URL Server

1. Verifica che l'URL sia corretto:
   - Dovrebbe essere: `https://google-workspace-mcp-osbdwu5a7q-uc.a.run.app`
   - NON includere `/mcp` (viene aggiunto automaticamente)

2. Testa l'URL direttamente:
   ```bash
   curl https://google-workspace-mcp-osbdwu5a7q-uc.a.run.app/health
   ```

### Soluzione 3: Verifica Chiave Crittografia

Se il token non può essere decriptato:

1. Verifica che `ENCRYPTION_KEY` sia configurato in Cloud Run
2. Deve essere la stessa chiave usata per salvare i token
3. Se cambiata, tutti i token devono essere riautenticati

## Prossimi Passi

Dopo aver identificato il problema:

1. **Se token scaduto**: Riautentica OAuth
2. **Se URL errato**: Aggiorna `server_url` nel database
3. **Se refresh fallisce**: Riautentica OAuth (refresh token potrebbe essere scaduto)
4. **Se token non valido**: Riautentica OAuth per ottenere token fresco

## Logs Utili

```bash
# Tutti i logs MCP/OAuth
gcloud run services logs read knowledge-navigator-backend \
  --region us-central1 \
  --limit 200 | grep -i "mcp\|oauth\|workspace"

# Logs errori
gcloud run services logs read knowledge-navigator-backend \
  --region us-central1 \
  --limit 200 | grep -i "error\|failed\|❌"

# Logs tool calls
gcloud run services logs read knowledge-navigator-backend \
  --region us-central1 \
  --limit 200 | grep -i "call_tool\|executing.*tool"
```

