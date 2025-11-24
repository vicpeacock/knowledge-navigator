# Google Workspace MCP Server - Deployment su Cloud Run

## ✅ Deployment Completato

Il Google Workspace MCP Server è stato deployato con successo su Cloud Run.

### Informazioni del Servizio

- **Service Name**: `google-workspace-mcp`
- **URL**: https://google-workspace-mcp-osbdwu5a7q-uc.a.run.app
- **Region**: `us-central1`
- **Project**: `knowledge-navigator-477022`

### OAuth Redirect URI

- **Redirect URI**: https://google-workspace-mcp-osbdwu5a7q-uc.a.run.app/oauth2callback

## ⚠️ Azione Richiesta: Aggiornare OAuth Credentials

**IMPORTANTE**: Devi aggiungere il redirect URI alle credenziali OAuth su Google Cloud Console:

1. Vai su: https://console.cloud.google.com/apis/credentials
2. Seleziona il progetto: `knowledge-navigator-477022`
3. Trova il tuo OAuth 2.0 Client ID (quello usato per `GOOGLE_OAUTH_CLIENT_ID`)
4. Clicca "Edit"
5. Nella sezione "Authorized redirect URIs", aggiungi:
   ```
   https://google-workspace-mcp-osbdwu5a7q-uc.a.run.app/oauth2callback
   ```
6. Salva le modifiche

## Come Connettersi al Server

### 1. Tramite Frontend

1. Accedi al frontend: https://knowledge-navigator-frontend-osbdwu5a7q-uc.a.run.app
2. Vai alla pagina **Integrations** (`/integrations`)
3. Nella sezione "Connect New MCP Server":
   - **Server URL**: `https://google-workspace-mcp-osbdwu5a7q-uc.a.run.app`
   - **Name**: `Google Workspace MCP` (opzionale)
4. Clicca "Connect"

### 2. Autenticazione OAuth

Dopo la connessione:

1. Vai alla pagina **Profile** (`/settings/profile`)
2. Trova l'integrazione "Google Workspace MCP"
3. Clicca "Authorize OAuth" per autenticarti con il tuo account Google
4. Autorizza l'accesso alle API Google Workspace necessarie

### 3. Seleziona i Tools

1. Vai alla pagina **Settings** → **Tools**
2. Trova "Google Workspace MCP" nella lista
3. Seleziona i tools che vuoi abilitare (Gmail, Calendar, Drive, Docs, Sheets, ecc.)

## Variabili d'Ambiente Configurate

Il servizio è configurato con:

- `GOOGLE_OAUTH_CLIENT_ID`: Configurato
- `GOOGLE_OAUTH_CLIENT_SECRET`: Configurato
- `GOOGLE_OAUTH_REDIRECT_URI`: https://google-workspace-mcp-osbdwu5a7q-uc.a.run.app/oauth2callback
- `MCP_ENABLE_OAUTH21=true`: OAuth 2.1 multi-user abilitato
- `EXTERNAL_OAUTH21_PROVIDER=true`: Modalità provider esterno
- `WORKSPACE_MCP_STATELESS_MODE=true`: Modalità stateless

## Risorse Cloud Run

- **Memory**: 512Mi
- **CPU**: 1
- **Timeout**: 300s
- **Max Instances**: 10
- **Port**: 8000 (gestita automaticamente da Cloud Run)

## Troubleshooting

### Il server non risponde

1. Verifica lo stato del servizio:
   ```bash
   gcloud run services describe google-workspace-mcp \
     --region us-central1 \
     --project knowledge-navigator-477022
   ```

2. Controlla i logs:
   ```bash
   gcloud run services logs read google-workspace-mcp \
     --region us-central1 \
     --project knowledge-navigator-477022
   ```

### Errore OAuth

- Verifica che il redirect URI sia aggiunto alle credenziali OAuth su Google Cloud Console
- Controlla che `GOOGLE_OAUTH_CLIENT_ID` e `GOOGLE_OAUTH_CLIENT_SECRET` siano corretti

### Tools non disponibili

- Verifica che l'autenticazione OAuth sia completata nella pagina Profile
- Controlla che i tools siano selezionati nelle preferenze utente (Settings > Tools)

## Riferimenti

- [Documentazione Connessione](./CONNECT_GOOGLE_WORKSPACE_MCP.md)
- [Setup Google Workspace MCP](../docs/GOOGLE_WORKSPACE_MCP_SETUP.md)
- [Script di Deployment](./deploy-workspace-mcp.sh)

