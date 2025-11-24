# Debug Google Consent Screen Block

## Problema
L'utente si blocca sulla pagina di consenso di Google (`accounts.google.com/signin/oauth/v2/consentsummary`). Quando clicca "Continue", Google non reindirizza al callback.

## Possibili Cause

### 1. Redirect URI non corrisponde esattamente
Google valida il `redirect_uri` passato nella richiesta di autorizzazione contro gli URI configurati su Google Cloud Console. Se non corrisponde **esattamente**, Google potrebbe:
- Bloccarsi sulla pagina di consenso
- Mostrare un errore (ma l'utente non lo vede)
- Non reindirizzare

### 2. Il redirect_uri non è presente nell'URL di autorizzazione
L'URL di autorizzazione generato dovrebbe contenere un parametro `redirect_uri`. Se manca, Google non sa dove reindirizzare.

### 3. Problema con l'encoding dell'URL
Il `redirect_uri` potrebbe essere URL-encoded in modo diverso da come è configurato su Google Cloud Console.

## Verifica

### 1. Controlla l'URL di Autorizzazione Generato
Quando clicchi "Authorize OAuth", l'URL di Google dovrebbe contenere un parametro `redirect_uri`. 

**Come verificare:**
1. Clicca "Authorize OAuth" nel frontend
2. Prima di essere reindirizzato a Google, controlla l'URL nella barra degli indirizzi
3. Cerca il parametro `redirect_uri` nell'URL
4. Verifica che corrisponda esattamente a:
   ```
   https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app/api/integrations/mcp/oauth/callback
   ```

### 2. Controlla i Log del Backend
Dopo aver cliccato "Authorize OAuth", controlla i log:
```bash
gcloud run services logs read knowledge-navigator-backend \
  --region us-central1 \
  --project knowledge-navigator-477022 \
  --limit 100 | grep -E "(OAuth authorize|redirect_uri|BASE_URL|authorization_url)"
```

Dovresti vedere:
```
🔵 OAuth authorize - Using redirect_uri: https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app/api/integrations/mcp/oauth/callback
```

### 3. Verifica su Google Cloud Console
L'URI configurato deve essere **esattamente**:
```
https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app/api/integrations/mcp/oauth/callback
```

**Verifica:**
- Nessun trailing slash (`/`)
- Protocollo `https://` (non `http://`)
- Case-sensitive
- Nessuno spazio o caratteri speciali

## Soluzione

### Opzione 1: Verifica che il redirect_uri sia nell'URL di autorizzazione
1. Clicca "Authorize OAuth"
2. Controlla l'URL di Google nella barra degli indirizzi
3. Cerca `redirect_uri=` nell'URL
4. Se non c'è, c'è un problema nella generazione dell'URL di autorizzazione

### Opzione 2: Verifica che BASE_URL sia corretto
Il backend usa `settings.base_url` per costruire il redirect_uri. Verifica che `BASE_URL` sia configurato su Cloud Run come:
```
https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app
```

### Opzione 3: Prova a rimuovere temporaneamente gli URI localhost
Anche se Google dovrebbe usare l'URI esatto passato, prova a:
1. Rimuovere temporaneamente gli URI localhost da Google Cloud Console
2. Riprovare l'autorizzazione OAuth
3. Se funziona, aggiungi di nuovo gli URI localhost

## Note

- Google OAuth valida il `redirect_uri` **prima** di mostrare la pagina di consenso
- Se il `redirect_uri` non corrisponde, Google potrebbe bloccarsi senza mostrare un errore
- Il `redirect_uri` deve essere URL-encoded quando passato nell'URL di autorizzazione

