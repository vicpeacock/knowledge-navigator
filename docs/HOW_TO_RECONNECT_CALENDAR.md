# Come Riconnettere Google Calendar

## Perché l'autorizzazione può essere scaduta?

L'autorizzazione Google Calendar può scadere per diversi motivi:

1. **Chiave di decriptazione cambiata**: Se `CREDENTIALS_ENCRYPTION_KEY` nel file `.env` è cambiata, le credenziali salvate non possono essere decriptate.

2. **Refresh token scaduto o revocato**: Google può revocare i token se:
   - L'utente revoca l'accesso manualmente su Google Account
   - Le impostazioni OAuth dell'applicazione cambiano
   - Il token non viene usato per molto tempo

3. **Credenziali corrotte**: Le credenziali salvate potrebbero essere corrotte o incomplete.

## Come Riconnettere

### Opzione 1: Tramite Frontend (Raccomandato)

1. Vai alla pagina **Integrations** (`/integrations`)
2. Trova la sezione **Google Calendar**
3. Clicca sul pulsante **"Ricollega Calendar"** (pulsante giallo/amber)
4. Verrai reindirizzato a Google per autorizzare l'accesso
5. Dopo l'autorizzazione, verrai reindirizzato di nuovo all'app

### Opzione 2: Tramite API Diretta

1. Chiama l'endpoint: `GET /api/integrations/calendars/oauth/authorize`
2. Se hai un'integrazione esistente, passa `integration_id` come parametro
3. Verrai reindirizzato a Google per autorizzare
4. Dopo l'autorizzazione, Google ti reindirizzerà a `/api/integrations/calendars/oauth/callback`

### Opzione 3: Eliminare e Ricreare

1. Vai alla pagina **Integrations**
2. Clicca su **"Rimuovi"** per eliminare l'integrazione esistente
3. Clicca su **"Connetti Google Calendar"** per crearne una nuova

## Verifica della Chiave di Decriptazione

Se la chiave di decriptazione è cambiata, devi:

1. Verificare che `CREDENTIALS_ENCRYPTION_KEY` nel file `.env.local` sia la stessa usata quando le credenziali sono state salvate
2. Se la chiave è cambiata, devi riconnettere tutte le integrazioni (email e calendario)

## Troubleshooting

### Errore: "Error decrypting credentials"

- **Causa**: La chiave di decriptazione è cambiata o le credenziali sono corrotte
- **Soluzione**: Riconnettere l'integrazione

### Errore: "Autorizzazione Google Calendar scaduta o revocata"

- **Causa**: Il refresh token è scaduto o è stato revocato da Google
- **Soluzione**: Riconnettere l'integrazione tramite OAuth

### Errore: "Nessuna integrazione Google Calendar configurata"

- **Causa**: Non c'è un'integrazione configurata per l'utente/tenant
- **Soluzione**: Creare una nuova integrazione tramite OAuth

## Note Importanti

- Quando riconnetti un'integrazione esistente, le vecchie credenziali vengono sostituite
- Il refresh token viene aggiornato durante la riconnessione
- Assicurati di avere `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET` configurati nel file `.env`

