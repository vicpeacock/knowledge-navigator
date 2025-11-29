# Fix MCP Tools su Cloud Run

## Problema

I tool MCP (come `mcp_list_calendars`) falliscono con errore perché l'integrazione MCP non è configurata nel database.

## Soluzione

Devi configurare l'integrazione Google Workspace MCP nel database. Ci sono due modi:

### Metodo 1: Tramite Frontend (Raccomandato)

1. **Accedi al Frontend**:
   - URL: https://knowledge-navigator-frontend-osbdwu5a7q-uc.a.run.app
   - Login con le tue credenziali

2. **Vai alla pagina Integrations**:
   - URL: https://knowledge-navigator-frontend-osbdwu5a7q-uc.a.run.app/integrations
   - Oppure clicca su "Integrations" nel menu

3. **Connetti Google Workspace MCP Server**:
   - Nella sezione "Connect New MCP Server":
     - **Server URL**: `https://google-workspace-mcp-osbdwu5a7q-uc.a.run.app`
     - **Name**: `Google Workspace MCP` (opzionale)
   - Clicca "Connect"

4. **Autentica OAuth**:
   - Vai alla pagina **Profile** (`/settings/profile`)
   - Trova l'integrazione "Google Workspace MCP"
   - Clicca "Authorize OAuth" per autenticarti con il tuo account Google
   - Autorizza l'accesso alle API Google Workspace necessarie

5. **Seleziona i Tools**:
   - Vai alla pagina **Settings** → **Tools**
   - Trova "Google Workspace MCP" nella lista
   - Seleziona i tools che vuoi abilitare (Calendar, Gmail, Drive, Docs, Sheets, Tasks)

### Metodo 2: Tramite API (Script)

Se preferisci configurare via API, puoi usare questo script:

```python
import requests
import json

# Configurazione
BACKEND_URL = "https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app"
MCP_SERVER_URL = "https://google-workspace-mcp-osbdwu5a7q-uc.a.run.app"
JWT_TOKEN = "your-jwt-token-here"  # Ottieni dal login

headers = {
    "Authorization": f"Bearer {JWT_TOKEN}",
    "Content-Type": "application/json"
}

# 1. Connetti MCP Server
response = requests.post(
    f"{BACKEND_URL}/api/integrations/mcp/connect",
    headers=headers,
    json={
        "server_url": MCP_SERVER_URL,
        "name": "Google Workspace MCP"
    }
)

if response.status_code == 200:
    integration = response.json()
    print(f"✅ MCP Server connesso: {integration['id']}")
    
    # 2. Autentica OAuth (se necessario)
    # Vai al frontend per autenticare OAuth manualmente
    # Oppure usa l'endpoint OAuth se disponibile
    
else:
    print(f"❌ Errore: {response.status_code} - {response.text}")
```

## Verifica Configurazione

### Verifica Integrazione MCP nel Database

Puoi verificare se l'integrazione è configurata correttamente:

```sql
-- Connetti a Supabase PostgreSQL
-- Query per verificare integrazioni MCP
SELECT 
    id,
    tenant_id,
    user_id,
    provider,
    service_type,
    enabled,
    session_metadata->>'server_url' as server_url
FROM integrations
WHERE service_type = 'mcp_server'
AND enabled = true;
```

### Verifica OAuth Token

L'utente deve avere un OAuth token valido per Google Workspace. Questo viene salvato nella tabella `integrations` con `credentials_encrypted`.

## Troubleshooting

### Errore: "Nessun conto Google autorizzato nel tuo profilo"

**Causa**: L'utente non ha un'integrazione MCP configurata o non ha autenticato OAuth.

**Soluzione**:
1. Verifica che l'integrazione MCP sia stata creata (vedi Metodo 1 o 2 sopra)
2. Verifica che l'utente abbia autenticato OAuth nella pagina Profile
3. Verifica che l'URL del server MCP sia corretto: `https://google-workspace-mcp-osbdwu5a7q-uc.a.run.app`

### Errore: "HTTP 404" o "Connection refused"

**Causa**: Il Google Workspace MCP Server non è raggiungibile.

**Soluzione**:
1. Verifica che il servizio sia deployato:
   ```bash
   gcloud run services describe google-workspace-mcp \
     --region us-central1 \
     --project knowledge-navigator-477022
   ```

2. Verifica che l'URL sia corretto nel database:
   ```sql
   SELECT session_metadata->>'server_url' 
   FROM integrations 
   WHERE service_type = 'mcp_server';
   ```

3. Testa l'URL direttamente:
   ```bash
   curl https://google-workspace-mcp-osbdwu5a7q-uc.a.run.app/health
   ```

### Errore: "OAuth authentication required"

**Causa**: L'utente non ha autenticato OAuth con Google.

**Soluzione**:
1. Vai alla pagina Profile (`/settings/profile`)
2. Trova l'integrazione "Google Workspace MCP"
3. Clicca "Authorize OAuth"
4. Completa il flusso OAuth con Google

### Errore: "Tool not found"

**Causa**: Il tool non è disponibile nel server MCP o non è selezionato nelle preferenze utente.

**Soluzione**:
1. Verifica che il tool sia disponibile nel server MCP:
   ```bash
   curl https://google-workspace-mcp-osbdwu5a7q-uc.a.run.app/mcp/tools \
     -H "Authorization: Bearer YOUR_OAUTH_TOKEN"
   ```

2. Verifica che il tool sia selezionato nelle preferenze utente (Settings > Tools)

## Configurazione Automatica (Script)

Puoi anche creare uno script per configurare automaticamente l'integrazione:

```bash
#!/bin/bash
# Script per configurare Google Workspace MCP su Cloud Run

BACKEND_URL="https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app"
MCP_SERVER_URL="https://google-workspace-mcp-osbdwu5a7q-uc.a.run.app"

echo "🔧 Configurazione Google Workspace MCP..."

# 1. Login e ottieni JWT token
echo "1. Effettua login al frontend e ottieni JWT token"
echo "   URL: ${BACKEND_URL}/api/v1/auth/login"
echo "   Usa le credenziali admin"

# 2. Connetti MCP Server
echo "2. Connetti MCP Server:"
echo "   POST ${BACKEND_URL}/api/integrations/mcp/connect"
echo "   Body: {\"server_url\": \"${MCP_SERVER_URL}\", \"name\": \"Google Workspace MCP\"}"

# 3. Autentica OAuth
echo "3. Autentica OAuth:"
echo "   Vai a: https://knowledge-navigator-frontend-osbdwu5a7q-uc.a.run.app/settings/profile"
echo "   Clicca 'Authorize OAuth' per Google Workspace MCP"

echo "✅ Configurazione completata!"
```

## Note Importanti

1. **OAuth Redirect URI**: Assicurati che il redirect URI sia configurato in Google Cloud Console:
   - `https://google-workspace-mcp-osbdwu5a7q-uc.a.run.app/oauth2callback`

2. **Per-User Integration**: Le integrazioni MCP sono per-utente (non globali). Ogni utente deve configurare la propria integrazione.

3. **OAuth Token**: Il token OAuth viene salvato criptato nel database. Ogni utente ha il proprio token.

4. **Tool Selection**: Gli utenti possono selezionare quali tools abilitare nelle preferenze (Settings > Tools).

## Prossimi Passi

Dopo aver configurato l'integrazione:

1. ✅ Verifica che `mcp_list_calendars` funzioni
2. ✅ Testa altri tool MCP (Gmail, Drive, etc.)
3. ✅ Verifica che le notifiche funzionino correttamente

