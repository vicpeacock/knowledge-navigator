# Fix: Error 400 redirect_uri_mismatch

## Problema

Google restituisce errore `400: redirect_uri_mismatch` perché il redirect URI non è registrato in Google Cloud Console.

## Soluzione

Devi aggiungere **entrambi** i redirect URI nelle impostazioni OAuth di Google Cloud Console.

### Passi da seguire:

1. **Vai su Google Cloud Console**
   - https://console.cloud.google.com/

2. **Seleziona il tuo progetto**

3. **Vai su APIs & Services > Credentials**

4. **Clicca sul tuo OAuth 2.0 Client ID** (quello che hai già creato)

5. **Nella sezione "Authorized redirect URIs"**, aggiungi questi **due URI**:

   ```
   http://localhost:8000/api/integrations/calendars/oauth/callback
   http://localhost:8000/api/integrations/emails/oauth/callback
   ```

   ⚠️ **IMPORTANTE**: 
   - Deve essere **esattamente** questi URI (niente slash finale)
   - Non devono avere spazi
   - Deve essere `http://localhost:8000` (non `https://`)

6. **Clicca "Save"**

7. **Aspetta 1-2 minuti** per la propagazione (a volte Google ci mette un po')

8. **Riprova** a connettere Calendar/Gmail

## Verifica degli URI nel Backend

Gli URI sono configurati in:
- `backend/app/core/config.py`:
  - `google_redirect_uri_calendar`
  - `google_redirect_uri_email`

Se li modifichi, assicurati di riavviare il backend.

## Se ricevi ancora Error 403: access_denied

Questo può succedere se:

1. **L'app non è verificata** (per uso personale/test):
   - Vai su **APIs & Services > OAuth consent screen**
   - Assicurati di aver aggiunto il tuo account email come "Test user"
   - L'app deve essere in modalità "Testing" per funzionare senza verifica

2. **Permessi mancanti**:
   - Verifica che Google Calendar API sia abilitata
   - Verifica che Gmail API sia abilitata (per le email)

## Checklist Completa

- [ ] Redirect URI calendario aggiunto: `http://localhost:8000/api/integrations/calendars/oauth/callback`
- [ ] Redirect URI email aggiunto: `http://localhost:8000/api/integrations/emails/oauth/callback`
- [ ] Google Calendar API abilitata
- [ ] Gmail API abilitata (se vuoi usare email)
- [ ] Account aggiunto come Test User nel consent screen
- [ ] OAuth consent screen configurato (nome app, email supporto)
- [ ] Backend riavviato dopo eventuali modifiche

## Test Rapido

Dopo aver aggiunto gli URI, puoi testare con:

```bash
# Test Calendar
curl "http://localhost:8000/api/integrations/calendars/oauth/authorize"

# Test Email  
curl "http://localhost:8000/api/integrations/emails/oauth/authorize"
```

Dovresti ricevere un JSON con `authorization_url` che puoi aprire nel browser.

