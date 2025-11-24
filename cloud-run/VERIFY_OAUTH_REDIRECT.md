# Verifica Configurazione OAuth Redirect URI

## ⚠️ Problema: OAuth si blocca dopo "Continue"

Se OAuth si blocca quando clicchi "Continue" sulla schermata di consenso Google, significa che il redirect URI non è configurato correttamente.

## Redirect URI Richiesto

Il redirect URI che DEVE essere aggiunto alle credenziali OAuth è:

```
https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app/api/integrations/mcp/oauth/callback
```

## Verifica Passo-Passo

### 1. Verifica che il Redirect URI sia Aggiunto

1. Vai su: https://console.cloud.google.com/apis/credentials
2. Seleziona il progetto: `knowledge-navigator-477022`
3. Trova il tuo OAuth 2.0 Client ID
4. Clicca per aprire i dettagli
5. **VERIFICA** che nella sezione "Authorized redirect URIs" ci sia:
   ```
   https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app/api/integrations/mcp/oauth/callback
   ```

### 2. Se NON è Presente, Aggiungilo

1. Clicca "Edit" (Modifica)
2. Nella sezione "Authorized redirect URIs", clicca "ADD URI"
3. Incolla esattamente:
   ```
   https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app/api/integrations/mcp/oauth/callback
   ```
4. **IMPORTANTE**: 
   - Deve essere `https://` (non `http://`)
   - Deve essere esattamente questo URL (case-sensitive)
   - Non deve avere trailing slash (`/`) alla fine
5. Clicca "SAVE" (Salva)
6. **Aspetta 1-2 minuti** per la propagazione delle modifiche

### 3. Verifica che BASE_URL sia Configurato

Il backend usa `BASE_URL` per costruire il redirect URI. Verifica che sia configurato:

```bash
# Controlla le variabili d'ambiente del backend su Cloud Run
gcloud run services describe knowledge-navigator-backend \
  --region us-central1 \
  --project knowledge-navigator-477022 \
  --format="value(spec.template.spec.containers[0].env)" | grep BASE_URL
```

Dovresti vedere:
```
BASE_URL=https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app
```

### 4. Test del Callback Endpoint

Il callback endpoint dovrebbe essere accessibile:

```bash
curl "https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app/api/integrations/mcp/oauth/callback?code=test&state=test"
```

Se ricevi un errore diverso da "Invalid state parameter" o "Google OAuth credentials not configured", c'è un problema con l'endpoint.

## Errori Comuni

### Errore: "redirect_uri_mismatch"
- **Causa**: Il redirect URI non è stato aggiunto o non corrisponde esattamente
- **Soluzione**: Aggiungi il redirect URI esatto come mostrato sopra

### Errore: "access_denied"
- **Causa**: Hai annullato l'autorizzazione
- **Soluzione**: Riprova e completa l'autorizzazione

### Errore: "invalid_client"
- **Causa**: Le credenziali OAuth non sono corrette
- **Soluzione**: Verifica `GOOGLE_OAUTH_CLIENT_ID` e `GOOGLE_OAUTH_CLIENT_SECRET`

### Il flusso si blocca senza errori
- **Causa**: Il redirect URI non è configurato o non corrisponde
- **Soluzione**: Verifica che il redirect URI sia esattamente quello mostrato sopra

## Checklist Finale

Prima di riprovare OAuth, verifica:

- [ ] Il redirect URI è aggiunto alle credenziali OAuth su Google Cloud Console
- [ ] Il redirect URI corrisponde esattamente (case-sensitive, no trailing slash)
- [ ] Hai aspettato 1-2 minuti dopo aver salvato le modifiche
- [ ] `BASE_URL` è configurato correttamente nel backend su Cloud Run
- [ ] Il callback endpoint è accessibile

## Dopo la Configurazione

1. **Riprova OAuth**:
   - Vai al frontend: https://knowledge-navigator-frontend-osbdwu5a7q-uc.a.run.app
   - Vai a Profile → Google Workspace MCP → Authorize OAuth
   - Clicca "Continue" sulla schermata di consenso Google

2. **Dovresti essere reindirizzato** al backend che completerà l'autorizzazione

3. **Se ancora si blocca**, controlla i logs del backend:
   ```bash
   gcloud run services logs read knowledge-navigator-backend \
     --region us-central1 \
     --project knowledge-navigator-477022 \
     --limit 100
   ```

