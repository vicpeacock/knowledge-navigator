# Debug OAuth Block su Google Consent Screen

## Problema
L'utente si blocca sulla pagina di consenso di Google (`accounts.google.com/signin/oauth/v2/consentsummary`). Quando clicca "Continue", Google non reindirizza al callback del backend.

## Possibili Cause

### 1. Redirect URI non configurato su Google Cloud Console
Il redirect URI deve essere **esattamente**:
```
https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app/api/integrations/mcp/oauth/callback
```

**Verifica:**
1. Vai su https://console.cloud.google.com/apis/credentials?project=knowledge-navigator-477022
2. Trova il Client ID: `526374196058-0vnk33472si9t07t6pttg8s7r4jmcuel.apps.googleusercontent.com`
3. Clicca per modificarlo
4. Verifica che nella sezione "Authorized redirect URIs" ci sia:
   ```
   https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app/api/integrations/mcp/oauth/callback
   ```

### 2. BASE_URL non configurato correttamente
Il backend usa `settings.base_url` per costruire il redirect URI. Verifica che `BASE_URL` sia configurato su Cloud Run come:
```
https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app
```

### 3. Errore nel callback quando Google reindirizza
Anche se Google reindirizza correttamente, il callback potrebbe fallire. Controlla i log del backend per vedere se il callback viene chiamato.

## Come Verificare

### Verifica Redirect URI su Google Cloud Console
```bash
# Il redirect URI deve essere esattamente:
https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app/api/integrations/mcp/oauth/callback
```

### Verifica BASE_URL su Cloud Run
```bash
gcloud run services describe knowledge-navigator-backend \
  --region us-central1 \
  --project knowledge-navigator-477022 \
  --format="value(spec.template.spec.containers[0].env)" | grep BASE_URL
```

### Verifica se il callback viene chiamato
```bash
gcloud run services logs read knowledge-navigator-backend \
  --region us-central1 \
  --project knowledge-navigator-477022 \
  --limit 100 | grep -i "oauth callback"
```

## Soluzione

1. **Aggiungi il redirect URI su Google Cloud Console** (se mancante)
2. **Verifica che BASE_URL sia configurato correttamente** su Cloud Run
3. **Riprova l'autorizzazione OAuth**
4. **Controlla i log** per vedere se il callback viene chiamato

## Note

- Il redirect URI è **case-sensitive**
- Non deve avere trailing slash (`/`)
- Deve usare `https://` (non `http://`)
- Deve corrispondere **esattamente** all'URL del backend su Cloud Run

