# Configurazione OAuth Redirect URI per Google Workspace MCP

## ⚠️ IMPORTANTE: Configurazione Richiesta

Per far funzionare l'autorizzazione OAuth del Google Workspace MCP server, devi aggiungere il redirect URI alle credenziali OAuth su Google Cloud Console.

## Redirect URI da Aggiungere

```
https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app/api/integrations/mcp/oauth/callback
```

## Istruzioni Passo-Passo

1. **Vai su Google Cloud Console**
   - URL: https://console.cloud.google.com/apis/credentials
   - Assicurati di essere nel progetto corretto: `knowledge-navigator-477022`

2. **Trova le Credenziali OAuth**
   - Cerca il tuo OAuth 2.0 Client ID (quello usato per `GOOGLE_OAUTH_CLIENT_ID`)
   - Dovrebbe essere: `526374196058-0vnk33472si9t07t6pttg8s7r4jmcuel.apps.googleusercontent.com`

3. **Modifica le Credenziali**
   - Clicca sul nome del Client ID per aprire i dettagli
   - Clicca "Edit" (Modifica)

4. **Aggiungi il Redirect URI**
   - Nella sezione "Authorized redirect URIs", clicca "ADD URI"
   - Aggiungi:
     ```
     https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app/api/integrations/mcp/oauth/callback
     ```
   - Clicca "SAVE" (Salva)

5. **Verifica**
   - Assicurati che il redirect URI sia presente nella lista
   - Dovresti vedere qualcosa come:
     ```
     https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app/api/integrations/mcp/oauth/callback
     ```

## Redirect URI già Configurati

Se hai già configurato redirect URI per altri servizi, potresti avere:
- `http://localhost:8003/oauth2callback` (per il Google Workspace MCP server locale)
- `https://google-workspace-mcp-osbdwu5a7q-uc.a.run.app/oauth2callback` (per il Google Workspace MCP server su Cloud Run)

**Questi sono diversi** dal redirect URI del backend che gestisce il callback OAuth per gli utenti.

## Dopo la Configurazione

Dopo aver aggiunto il redirect URI:

1. **Riprova l'Autorizzazione OAuth**
   - Vai al frontend: https://knowledge-navigator-frontend-osbdwu5a7q-uc.a.run.app
   - Vai alla pagina Profile (`/settings/profile`)
   - Trova l'integrazione "Google Workspace MCP"
   - Clicca "Authorize OAuth"

2. **Completa il Flusso OAuth**
   - Dovresti essere reindirizzato a Google per autorizzare
   - Dopo l'autorizzazione, verrai reindirizzato al backend
   - Il backend salverà le credenziali OAuth per il tuo account

## Troubleshooting

### Errore: "redirect_uri_mismatch"
- **Causa**: Il redirect URI non è stato aggiunto alle credenziali OAuth
- **Soluzione**: Segui le istruzioni sopra per aggiungere il redirect URI

### Errore: "access_denied"
- **Causa**: Hai annullato l'autorizzazione su Google
- **Soluzione**: Riprova e completa l'autorizzazione

### Errore: "invalid_client"
- **Causa**: Le credenziali OAuth (`GOOGLE_OAUTH_CLIENT_ID` e `GOOGLE_OAUTH_CLIENT_SECRET`) non sono corrette
- **Soluzione**: Verifica che le credenziali nel file `.env.cloud-run` corrispondano a quelle su Google Cloud Console

## Note

- Il redirect URI deve corrispondere **esattamente** all'URL del backend su Cloud Run
- Non includere trailing slash (`/`) alla fine
- Assicurati di usare `https://` (non `http://`)
- Il redirect URI è case-sensitive

