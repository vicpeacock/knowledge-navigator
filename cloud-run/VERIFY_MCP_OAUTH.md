# Verifica Autorizzazione OAuth MCP

## Metodo 1: Script Automatico (Raccomandato)

```bash
cd cloud-run
./check-mcp-oauth-status.sh
```

Lo script:
1. Fa login con le tue credenziali
2. Recupera le integrazioni MCP
3. Testa la connessione per ogni integrazione
4. Verifica se i tools sono disponibili (indica se OAuth è autorizzato)

## Metodo 2: Tramite API Diretta

### 1. Login e Ottieni Token

```bash
BACKEND_URL="https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app"

# Login
LOGIN_RESPONSE=$(curl -s -X POST "${BACKEND_URL}/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "your-email@example.com", "password": "your-password"}')

ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)
```

### 2. Lista Integrazioni MCP

```bash
curl -s -X GET "${BACKEND_URL}/api/integrations/mcp/integrations" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" | python3 -m json.tool
```

### 3. Test Connessione per Integrazione

```bash
INTEGRATION_ID="your-integration-id"

curl -s -X POST "${BACKEND_URL}/api/integrations/mcp/${INTEGRATION_ID}/test" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" | python3 -m json.tool
```

**Risposta attesa se OAuth è autorizzato**:
```json
{
  "status": "connected",
  "oauth_required": true,
  "server_url": "https://google-workspace-mcp-osbdwu5a7q-uc.a.run.app",
  "tools_count": 20,
  "tools": [...]
}
```

**Risposta se OAuth NON è autorizzato**:
```json
{
  "status": "connected",
  "oauth_required": true,
  "server_url": "https://google-workspace-mcp-osbdwu5a7q-uc.a.run.app",
  "tools_count": 0,
  "tools": [],
  "message": "Server is reachable. OAuth 2.1 authentication required..."
}
```

### 4. Debug Info per Integrazione

```bash
curl -s -X GET "${BACKEND_URL}/api/integrations/mcp/${INTEGRATION_ID}/debug" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" | python3 -m json.tool
```

### 5. Lista Tools Disponibili

```bash
curl -s -X GET "${BACKEND_URL}/api/integrations/mcp/${INTEGRATION_ID}/tools" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" | python3 -m json.tool
```

**Se OAuth è autorizzato**: `available_tools` contiene la lista dei tools  
**Se OAuth NON è autorizzato**: `available_tools` è vuoto

## Metodo 3: Tramite Frontend

1. **Vai alla pagina Profile**:
   - URL: https://knowledge-navigator-frontend-osbdwu5a7q-uc.a.run.app/settings/profile
   - Login con le tue credenziali

2. **Cerca "Google Workspace MCP"**:
   - Dovresti vedere lo stato dell'autorizzazione
   - Se non autorizzato, vedrai un pulsante "Authorize OAuth"
   - Se autorizzato, vedrai l'email Google associata

3. **Vai alla pagina Integrations**:
   - URL: https://knowledge-navigator-frontend-osbdwu5a7q-uc.a.run.app/integrations
   - Verifica che l'integrazione MCP sia presente e abilitata

## Metodo 4: Verifica Database Diretta

```sql
-- Connetti a Supabase PostgreSQL
-- Verifica OAuth credentials salvate

SELECT 
    id,
    user_id,
    enabled,
    session_metadata->>'server_url' as server_url,
    jsonb_object_keys(session_metadata->'oauth_credentials') as oauth_user_ids,
    session_metadata->'oauth_user_emails' as oauth_user_emails
FROM integrations
WHERE service_type = 'mcp_server'
AND enabled = true
AND user_id = 'YOUR_USER_ID_HERE';
```

**Se OAuth è autorizzato**:
- `oauth_user_ids` contiene il tuo `user_id`
- `oauth_user_emails` contiene la tua email Google

**Se OAuth NON è autorizzato**:
- `oauth_credentials` è vuoto o non contiene il tuo `user_id`

## Interpretazione Risultati

### ✅ OAuth Autorizzato
- `tools_count > 0` nel test
- `available_tools` non vuoto
- `oauth_credentials` contiene il tuo `user_id` nel database
- Frontend mostra email Google nel Profile

### ⚠️ OAuth NON Autorizzato
- `tools_count = 0` nel test
- `available_tools` vuoto
- `oauth_credentials` vuoto o non contiene il tuo `user_id`
- Frontend mostra pulsante "Authorize OAuth"

## Prossimi Passi

### Se OAuth NON è autorizzato:

1. **Vai al Frontend**:
   - Profile → Google Workspace MCP → "Authorize OAuth"

2. **Completa il flusso OAuth**:
   - Autorizza l'accesso alle API Google Workspace
   - Attendi il redirect

3. **Verifica di nuovo**:
   - Esegui lo script di verifica
   - Controlla che `tools_count > 0`

### Se OAuth è autorizzato ma i tools non funzionano:

1. **Verifica che i tools siano selezionati**:
   - Settings → Tools → Seleziona i tools Google Workspace

2. **Verifica logs backend**:
   ```bash
   gcloud run services logs read knowledge-navigator-backend \
     --region us-central1 \
     --limit 50 | grep -i "mcp\|oauth"
   ```

3. **Testa un tool direttamente**:
   - Prova `mcp_list_calendars` nella chat
   - Verifica i logs per errori specifici

