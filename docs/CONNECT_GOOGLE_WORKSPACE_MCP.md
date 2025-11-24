# Come Connettersi al Google Workspace MCP Server

## Panoramica

Il Google Workspace MCP Server ti permette di usare tutti i servizi Google Workspace (Gmail, Calendar, Drive, Docs, Sheets, ecc.) tramite il Knowledge Navigator.

## Prerequisiti

1. **Google Workspace MCP Server in esecuzione**
   - Il server deve essere accessibile dal backend
   - URL di default: `http://localhost:8003` (locale) o `http://host.docker.internal:8003` (da Docker)

2. **Credenziali OAuth configurate** (opzionale, solo se vuoi usare OAuth)
   - `GOOGLE_OAUTH_CLIENT_ID`
   - `GOOGLE_OAUTH_CLIENT_SECRET`

## Procedura di Connessione

### Opzione 1: Tramite Frontend (Consigliato)

1. **Accedi al frontend**
   - Vai su: https://knowledge-navigator-frontend-osbdwu5a7q-uc.a.run.app
   - Fai login con `admin@example.com` / `admin123`

2. **Vai alla pagina Integrations**
   - Clicca su "Integrations" nel menu
   - Oppure vai direttamente a: `/integrations`

3. **Connetti il Google Workspace MCP Server**
   - Nella sezione "MCP Servers", trova "Connect New MCP Server"
   - **Server URL**: Inserisci l'URL del server MCP
     - Per server locale: `http://localhost:8003`
     - Per server su Cloud Run: `https://your-mcp-server-url.run.app`
   - **Name** (opzionale): Inserisci un nome descrittivo, es. "Google Workspace MCP"
   - Clicca su "Connect"

4. **Autenticazione OAuth** (se richiesta)
   - Dopo la connessione, se vedi "OAuth authentication required"
   - Vai alla pagina Profile (`/settings/profile`)
   - Trova l'integrazione Google Workspace MCP
   - Clicca su "Authorize OAuth" per autenticarti con il tuo account Google

### Opzione 2: Tramite API (Avanzato)

Puoi connettere il server anche tramite API:

```bash
curl -X POST "https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app/api/integrations/mcp/connect" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "server_url": "http://localhost:8003",
    "name": "Google Workspace MCP"
  }'
```

## URL del Server MCP

### Ambiente Locale
- **URL**: `http://localhost:8003`
- Il server deve essere in esecuzione localmente

### Ambiente Docker
- **URL**: `http://host.docker.internal:8003` (se il backend è in Docker)
- Oppure usa l'IP del container Docker

### Ambiente Cloud Run
- **URL**: `https://your-mcp-server-url.run.app` (se hai deployato il server su Cloud Run)
- Assicurati che il server sia accessibile pubblicamente o che ci sia una connessione privata

## Verifica Connessione

Dopo la connessione:

1. **Controlla lo stato**
   - Nella pagina Integrations, dovresti vedere il server MCP nella lista
   - Lo stato dovrebbe essere "Connected" o "OAuth Required"

2. **Verifica i tools disponibili**
   - Vai alla pagina Settings > Tools
   - Dovresti vedere i tools di Google Workspace (Gmail, Calendar, Drive, ecc.)
   - I tools sono raggruppati per servizio (Gmail, Calendar, Drive, ecc.)

3. **Testa un tool**
   - Crea una nuova sessione
   - Prova a chiedere: "Mostrami le email recenti" o "Quali eventi ho nel calendario?"

## Troubleshooting

### Errore: "Server URL non può essere vuoto"
- Assicurati di aver inserito un URL valido che inizia con `http://` o `https://`

### Errore: "Connection refused" o "Cannot connect"
- Verifica che il Google Workspace MCP Server sia in esecuzione
- Controlla che l'URL sia corretto
- Se il backend è su Cloud Run e il server è locale, devi deployare anche il server MCP o usare un tunnel

### Errore: "OAuth authentication required"
- Questo è normale per il Google Workspace MCP Server
- Vai alla pagina Profile e autorizza OAuth
- Dopo l'autorizzazione, i tools saranno disponibili

### Tools non disponibili
- Verifica che l'autenticazione OAuth sia completata
- Controlla che i tools siano selezionati nelle preferenze utente (Settings > Tools)
- Assicurati che l'integrazione sia abilitata

## Note Importanti

1. **Multi-User**: Ogni utente deve autenticarsi separatamente con il proprio account Google
2. **OAuth 2.1**: Il Google Workspace MCP Server usa OAuth 2.1 per l'autenticazione
3. **Tools Disponibili**: Dopo la connessione e l'autenticazione OAuth, avrai accesso a ~83 tools di Google Workspace
4. **Server URL**: Se il server è su Cloud Run, usa l'URL HTTPS completo

## Prossimi Step

Dopo aver connesso il server:
1. ✅ Autorizza OAuth (se richiesto)
2. ✅ Seleziona i tools che vuoi usare (Settings > Tools)
3. ✅ Inizia a usare i tools nelle tue sessioni!

