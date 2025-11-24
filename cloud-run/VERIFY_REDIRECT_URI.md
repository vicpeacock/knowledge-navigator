# Verifica Redirect URI OAuth

## Problema
L'utente si blocca sulla pagina di consenso di Google. Potrebbe essere che il `redirect_uri` passato a Google non corrisponda esattamente a quello configurato.

## Requisiti Google per Redirect URI
- Deve avere un protocollo (https://)
- Non può contenere URL fragments, relative paths, o wildcards
- Non può essere un indirizzo IP pubblico
- Deve corrispondere **esattamente** a uno degli URI configurati su Google Cloud Console

## Verifica

### 1. Controlla i Log del Backend
Dopo aver cliccato "Authorize OAuth", controlla i log:
```bash
gcloud run services logs read knowledge-navigator-backend \
  --region us-central1 \
  --project knowledge-navigator-477022 \
  --limit 100 | grep -E "(OAuth authorize|redirect_uri|BASE_URL)"
```

Dovresti vedere:
```
🔵 OAuth authorize - Using redirect_uri: https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app/api/integrations/mcp/oauth/callback
```

### 2. Verifica su Google Cloud Console
L'URI configurato deve essere **esattamente**:
```
https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app/api/integrations/mcp/oauth/callback
```

### 3. Verifica nell'URL di Autorizzazione
Quando clicchi "Authorize OAuth", l'URL di Google dovrebbe contenere un parametro `redirect_uri` che corrisponde esattamente all'URI configurato.

## Possibili Problemi

### Problema 1: BASE_URL non configurato correttamente
Se `BASE_URL` non è configurato su Cloud Run, il backend userà il default `http://localhost:8000`, che non corrisponde all'URI configurato.

**Soluzione**: Verifica che `BASE_URL` sia configurato su Cloud Run come:
```
https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app
```

### Problema 2: Differenze di case o trailing slash
L'URI deve corrispondere **esattamente**, incluso:
- Case-sensitive
- Nessun trailing slash
- Protocollo corretto (https://)

### Problema 3: URI localhost interferisce
Anche se Google dovrebbe usare l'URI esatto passato nella richiesta, gli URI localhost potrebbero causare problemi.

**Soluzione**: Prova a rimuovere temporaneamente gli URI localhost e vedere se funziona.

## Test
1. Prova l'autorizzazione OAuth
2. Controlla i log per vedere quale `redirect_uri` viene usato
3. Verifica che corrisponda esattamente all'URI configurato su Google Cloud Console
4. Se non corrisponde, verifica `BASE_URL` su Cloud Run

