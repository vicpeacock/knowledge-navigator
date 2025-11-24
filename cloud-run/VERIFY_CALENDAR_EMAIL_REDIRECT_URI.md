# Verifica Redirect URI per Calendar e Email OAuth

## Problema
Errore `redirect_uri_mismatch` quando si prova a connettere Calendar o Email.

## Soluzione

### 1. Verifica i Redirect URI configurati in Google Cloud Console

1. Vai su [Google Cloud Console](https://console.cloud.google.com/)
2. Seleziona il progetto: `knowledge-navigator-477022`
3. Vai su **APIs & Services** > **Credentials**
4. Clicca sull'OAuth 2.0 Client ID: `526374196058-0vnk33472si9t07t6pttg8s7r4jmcuel.apps.googleusercontent.com`
5. Verifica che i seguenti **Authorized redirect URIs** siano presenti:

```
https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app/api/integrations/calendars/oauth/callback
https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app/api/integrations/emails/oauth/callback
```

### 2. Verifica i Log del Backend

Dopo aver provato a connettere Calendar, controlla i log per vedere quale `redirect_uri` viene effettivamente generato:

```bash
gcloud run services logs read knowledge-navigator-backend \
  --region us-central1 \
  --project knowledge-navigator-477022 \
  --limit 100 | grep -E "(Calendar OAuth|Email OAuth|redirect_uri)"
```

Dovresti vedere qualcosa come:
```
🔵 Calendar OAuth - Using redirect_uri: https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app/api/integrations/calendars/oauth/callback
```

### 3. Se il Redirect URI non corrisponde

Se il `redirect_uri` nei log non corrisponde esattamente a quello in Google Cloud Console:

1. **Copia esattamente** il `redirect_uri` dai log
2. **Aggiungilo** in Google Cloud Console come Authorized redirect URI
3. **Salva** le modifiche
4. **Attendi 1-2 minuti** per la propagazione
5. **Riprova** la connessione

### 4. Verifica che BASE_URL sia configurato correttamente

Verifica che `BASE_URL` sia configurato in Cloud Run:

```bash
gcloud run services describe knowledge-navigator-backend \
  --region us-central1 \
  --project knowledge-navigator-477022 \
  --format="value(spec.template.spec.containers[0].env)" | grep BASE_URL
```

Dovresti vedere:
```
BASE_URL=https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app
```

### 5. Redirect URI per Sviluppo Locale (opzionale)

Se vuoi anche supportare lo sviluppo locale, aggiungi anche:

```
http://localhost:8000/api/integrations/calendars/oauth/callback
http://localhost:8000/api/integrations/emails/oauth/callback
```

## Note Importanti

- Il `redirect_uri` deve corrispondere **esattamente** (case-sensitive, no trailing slash)
- Google può richiedere 1-2 minuti per propagare le modifiche
- Se usi un dominio personalizzato, assicurati che sia configurato anche quello

