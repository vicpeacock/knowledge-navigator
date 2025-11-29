# Debug MCP Connection - Guida

## Problema

Dopo l'autorizzazione OAuth di Google Workspace MCP, il backend non si connette al server MCP.

## Diagnostica

### 1. Esegui Script di Debug

```bash
cd backend
source venv/bin/activate  # O il tuo ambiente virtuale
python ../cloud-run/debug-mcp-connection.py
```

Lo script verificherà:
- ✅ Integrazioni MCP nel database
- ✅ OAuth tokens salvati
- ✅ Creazione MCP client
- ✅ Connessione al server MCP
- ✅ Lista tools disponibili

### 2. Verifica Manuale nel Database

```sql
-- Connetti a Supabase PostgreSQL
-- Verifica integrazioni MCP
SELECT 
    id,
    tenant_id,
    user_id,
    enabled,
    session_metadata->>'server_url' as server_url,
    jsonb_object_keys(session_metadata->'oauth_credentials') as oauth_user_ids
FROM integrations
WHERE service_type = 'mcp_server'
AND enabled = true;

-- Verifica OAuth credentials per un utente specifico
SELECT 
    id,
    session_metadata->'oauth_credentials'->'USER_ID_QUI' as oauth_creds,
    session_metadata->'oauth_user_emails'->'USER_ID_QUI' as user_email
FROM integrations
WHERE service_type = 'mcp_server'
AND id = 'INTEGRATION_ID_QUI';
```

### 3. Verifica Logs Backend

```bash
# Cloud Run logs
gcloud run services logs read knowledge-navigator-backend \
  --region us-central1 \
  --project knowledge-navigator-477022 \
  --limit 100 | grep -i "mcp\|oauth\|workspace"
```

Cerca:
- `✅ Retrieved OAuth access token`
- `Created MCP client with OAuth token`
- `Error connecting to MCP server`
- `HTTP 404` o `HTTP 401`

## Problemi Comuni e Soluzioni

### Problema 1: Token OAuth Non Salvato

**Sintomi**:
- Script di debug mostra "Token non trovato"
- `oauth_credentials` è vuoto nel database

**Soluzione**:
1. Verifica che l'autorizzazione OAuth sia completata
2. Controlla i logs del callback OAuth:
   ```bash
   gcloud run services logs read knowledge-navigator-backend \
     --region us-central1 \
     --limit 50 | grep "OAuth callback"
   ```
3. Verifica che `credentials_encryption_key` sia configurato correttamente in Cloud Run

### Problema 2: URL Server MCP Errato

**Sintomi**:
- `HTTP 404` nei logs
- "Endpoint MCP non trovato"

**Soluzione**:
1. Verifica che l'URL sia corretto:
   ```sql
   SELECT session_metadata->>'server_url' 
   FROM integrations 
   WHERE service_type = 'mcp_server';
   ```
2. Dovrebbe essere: `https://google-workspace-mcp-osbdwu5a7q-uc.a.run.app`
3. Il client aggiunge automaticamente `/mcp` alla fine, quindi non includerlo nell'URL salvato

### Problema 3: Token OAuth Scaduto

**Sintomi**:
- `HTTP 401 Unauthorized`
- "Invalid token" nei logs

**Soluzione**:
1. Riautentica OAuth:
   - Vai a Profile → Google Workspace MCP → "Revoke OAuth"
   - Poi "Authorize OAuth" di nuovo
2. Verifica che il refresh token sia salvato correttamente

### Problema 4: Server MCP Non Raggiungibile

**Sintomi**:
- `Connection refused` o `Timeout`
- Server non risponde

**Soluzione**:
1. Verifica che il server sia deployato:
   ```bash
   gcloud run services describe google-workspace-mcp \
     --region us-central1 \
     --project knowledge-navigator-477022
   ```
2. Testa l'URL direttamente:
   ```bash
   curl https://google-workspace-mcp-osbdwu5a7q-uc.a.run.app/health
   ```
3. Verifica che il server sia in esecuzione e raggiungibile

### Problema 5: Chiave di Crittografia Non Configurata

**Sintomi**:
- "Could not decrypt OAuth credentials"
- Token non recuperabile

**Soluzione**:
1. Verifica che `ENCRYPTION_KEY` sia configurato in Cloud Run:
   ```bash
   gcloud run services describe knowledge-navigator-backend \
     --region us-central1 \
     --format "value(spec.template.spec.containers[0].env)"
   ```
2. Deve essere la stessa chiave usata per salvare i token
3. Se cambiata, tutti i token devono essere riautenticati

## Test Manuale

### Test 1: Verifica Integrazione nel Database

```python
# In Python shell o script
from app.models.database import Integration
from sqlalchemy import select

# Query integrazione MCP
integration = await db.execute(
    select(Integration)
    .where(Integration.service_type == "mcp_server")
    .where(Integration.enabled == True)
    .where(Integration.user_id == YOUR_USER_ID)
).scalar_one_or_none()

if integration:
    print(f"Server URL: {integration.session_metadata.get('server_url')}")
    print(f"OAuth credentials: {list(integration.session_metadata.get('oauth_credentials', {}).keys())}")
```

### Test 2: Test Connessione Diretta

```python
from app.core.mcp_client import MCPClient

# Test senza OAuth (per vedere se il server risponde)
client = MCPClient(
    base_url="https://google-workspace-mcp-osbdwu5a7q-uc.a.run.app",
    use_auth_token=False
)

try:
    tools = await client.list_tools()
    print(f"Tools: {len(tools)}")
except Exception as e:
    print(f"Error: {e}")
```

### Test 3: Test con OAuth Token

```python
from app.api.integrations.mcp import _get_mcp_client_for_integration

# Usa integrazione dal database
client = _get_mcp_client_for_integration(integration, current_user=user)

try:
    tools = await client.list_tools()
    print(f"Tools: {len(tools)}")
except Exception as e:
    print(f"Error: {e}")
```

## Prossimi Passi

Dopo aver identificato il problema:

1. **Se token non salvato**: Riautentica OAuth
2. **Se URL errato**: Aggiorna `server_url` nel database
3. **Se token scaduto**: Riautentica OAuth
4. **Se server non raggiungibile**: Verifica deployment del server MCP
5. **Se chiave errata**: Configura `ENCRYPTION_KEY` correttamente

## Logs Utili

```bash
# Tutti i logs MCP
gcloud run services logs read knowledge-navigator-backend \
  --region us-central1 \
  --limit 200 | grep -i "mcp"

# Logs OAuth
gcloud run services logs read knowledge-navigator-backend \
  --region us-central1 \
  --limit 200 | grep -i "oauth"

# Logs errori
gcloud run services logs read knowledge-navigator-backend \
  --region us-central1 \
  --limit 200 | grep -i "error\|failed\|❌"
```

