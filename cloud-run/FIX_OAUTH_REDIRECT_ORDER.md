# Fix OAuth Redirect URI Order

## Problema
Gli URI localhost potrebbero interferire con il flusso OAuth su Cloud Run. Google potrebbe provare gli URI in ordine o verificare la loro validità.

## Soluzione

### Opzione 1: Rimuovere gli URI localhost (Consigliato)
1. Vai su Google Cloud Console → Credentials
2. Modifica il Client ID OAuth
3. **Rimuovi** questi URI localhost:
   - `http://localhost:8000/api/integrations/calendars/oauth/callback`
   - `http://localhost:8000/api/integrations/emails/oauth/callback`
   - `http://localhost:8000/api/integrations/mcp/oauth/callback`
4. **Mantieni solo** gli URI di Cloud Run:
   - `https://google-workspace-mcp-osbdwu5a7q-uc.a.run.app/oauth2callback`
   - `https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app/api/integrations/mcp/oauth/callback`
5. Salva

### Opzione 2: Spostare l'URI Cloud Run in cima
1. Modifica il Client ID OAuth
2. Usa "Add URI" per aggiungere l'URI Cloud Run
3. Elimina e riaggiungi gli URI localhost dopo
4. In questo modo l'URI Cloud Run sarà il primo nella lista

## Verifica
Dopo aver modificato gli URI:
1. Attendi 1-2 minuti per la propagazione
2. Riprova l'autorizzazione OAuth
3. Dovresti essere reindirizzato correttamente

## Nota
Gli URI localhost sono utili solo per sviluppo locale. Per produzione su Cloud Run, non sono necessari e potrebbero causare problemi.

