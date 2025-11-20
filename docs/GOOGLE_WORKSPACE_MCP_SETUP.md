# Google Workspace MCP Server - Setup e Configurazione Multi-User

## Panoramica

Il Google Workspace MCP Server permette di integrare Google Workspace (Gmail, Calendar, Drive, Docs, Sheets, ecc.) tramite il protocollo MCP. Il server supporta **OAuth 2.1 multi-user**, permettendo a ogni utente di autenticarsi con il proprio account Google.

## Architettura Multi-User

### Credenziali OAuth dell'Applicazione (Condivise)
- **`GOOGLE_OAUTH_CLIENT_ID`** e **`GOOGLE_OAUTH_CLIENT_SECRET`**: Credenziali dell'applicazione registrata su Google Cloud Console
- Queste credenziali identificano la tua applicazione, non un account Google specifico
- Sono condivise da tutti gli utenti del sistema

### Autenticazione per Utente (Separata)
- Ogni utente si autentica con il proprio account Google quando usa i tools del server MCP
- I token OAuth vengono gestiti dal server MCP stesso (non nel database del Knowledge Navigator)
- Ogni utente vede solo i propri dati (email, calendario, file Drive, ecc.)

## Configurazione

### 1. Registra l'Applicazione su Google Cloud Console

1. Vai su [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un nuovo progetto o seleziona uno esistente
3. Abilita le API necessarie:
   - Gmail API
   - Google Calendar API
   - Google Drive API
   - Google Docs API
   - Google Sheets API
   - (altre API Google Workspace che vuoi usare)
4. Crea credenziali OAuth 2.0:
   - Tipo: "OAuth client ID"
   - Tipo applicazione: "Web application"
   - Authorized redirect URIs: `http://localhost:8003/oauth2callback` (per sviluppo locale)
   - Per produzione: aggiungi anche `https://your-domain.com/oauth2callback`

### 2. Configura le Variabili d'Ambiente

Aggiungi al file `.env` nella root del progetto:

```bash
# Credenziali OAuth dell'applicazione (condivise)
GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
```

**Nota**: Puoi usare le stesse credenziali di `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET` (usate per le integrazioni Gmail/Calendar dirette) oppure crearne di separate per il Google Workspace MCP Server.

### 3. Build e Avvio del Servizio Docker

```bash
# Build dell'immagine
docker-compose build google-workspace-mcp

# Avvia il servizio
docker-compose up -d google-workspace-mcp

# Verifica che sia in esecuzione
docker-compose ps
curl http://localhost:8002/health
```

### 4. Aggiungi l'Integrazione tramite Frontend

1. Vai su `/integrations` nel frontend
2. Clicca "Aggiungi Integrazione" → "MCP Server"
3. Compila il form:
   - **Nome**: `Google Workspace MCP`
   - **URL Server**: `http://localhost:8003`
   - **Tipo**: `mcp_server`
4. Salva l'integrazione

### 5. Seleziona i Tools Disponibili

1. Vai su `/settings/tools` nel frontend
2. Trova "Google Workspace MCP" nella lista
3. Seleziona i tools che vuoi abilitare (es. `gmail_send`, `calendar_list_events`, `drive_list_files`, ecc.)

## Come Funziona l'Autenticazione Multi-User

### Primo Utilizzo di un Tool

Quando un utente usa per la prima volta un tool del Google Workspace MCP server:

1. Il server MCP rileva che l'utente non è autenticato
2. Reindirizza l'utente al flusso OAuth di Google
3. L'utente autorizza l'accesso al proprio account Google
4. Il server MCP salva i token OAuth per quell'utente
5. I tool vengono eseguiti con i dati dell'utente autenticato

### Utilizzi Successivi

- I token OAuth vengono riutilizzati automaticamente
- Se un token scade, il server MCP usa il refresh token per ottenerne uno nuovo
- Ogni utente ha i propri token, isolati dagli altri utenti

## Differenza con Integrazioni Gmail/Calendar Dirette

| Aspetto | Integrazioni Gmail/Calendar | Google Workspace MCP Server |
|---------|----------------------------|----------------------------|
| **Storage Token** | Database Knowledge Navigator (`Integration.credentials_encrypted`) | Server MCP stesso |
| **Gestione Multi-User** | Manuale (un'integrazione per utente) | Automatica (OAuth 2.1 multi-user) |
| **Tools Disponibili** | Solo Gmail e Calendar | Gmail, Calendar, Drive, Docs, Sheets, ecc. |
| **Configurazione** | Richiede setup per ogni utente | Setup una volta, ogni utente si autentica automaticamente |

## Troubleshooting

### Il server non parte

```bash
# Verifica i logs
docker-compose logs google-workspace-mcp

# Verifica le variabili d'ambiente
docker-compose exec google-workspace-mcp env | grep GOOGLE

# Verifica che il servizio sia in esecuzione
curl http://localhost:8003/health
```

### Errore "OAuth credentials not configured"

- Verifica che `GOOGLE_OAUTH_CLIENT_ID` e `GOOGLE_OAUTH_CLIENT_SECRET` siano nel `.env`
- Riavvia il container: `docker-compose restart google-workspace-mcp`

### Utente non può autenticarsi

- Verifica che l'URL di redirect sia corretto: `http://localhost:8003/oauth2callback`
- Verifica che le API necessarie siano abilitate su Google Cloud Console
- Controlla i logs del server MCP per errori OAuth

### Tools non visibili nel frontend

- Verifica che l'integrazione sia abilitata (`enabled: true`)
- Verifica che l'URL del server sia corretto (`http://localhost:8003`)
- Controlla i logs del backend per errori di connessione al server MCP

## Produzione (Cloud Run)

Per il deployment su Cloud Run:

1. Aggiorna `GOOGLE_OAUTH_REDIRECT_URI` nel `docker-compose.yml` o `cloud-run/deploy.sh`:
   ```bash
   GOOGLE_OAUTH_REDIRECT_URI=https://your-workspace-mcp-domain.com/oauth2callback
   ```
   **Nota**: Per sviluppo locale, usa `http://localhost:8003/oauth2callback`

2. Aggiungi l'URL di produzione alle "Authorized redirect URIs" su Google Cloud Console

3. Deploy del servizio Google Workspace MCP su Cloud Run (separato dal backend/frontend)

4. Aggiorna l'URL dell'integrazione nel database per puntare all'URL di produzione

## Riferimenti

- [Google Workspace MCP Server GitHub](https://github.com/taylorwilsdon/google_workspace_mcp)
- [Quick Start Guide](https://workspacemcp.com/quick-start)
- [Google Cloud Console](https://console.cloud.google.com/)
- [OAuth 2.0 Documentation](https://developers.google.com/identity/protocols/oauth2)

