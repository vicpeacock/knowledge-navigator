# Troubleshooting: Errore "Service(s) not found or permission denied" per Calendar API

## Problema
Quando provi ad abilitare Google Calendar API, ricevi l'errore:
```
Service(s) not found or permission denied
Not found or permission denied for one or more service(s).
```

## Cause Possibili

### 1. Permessi Insufficienti
Non hai i permessi necessari per abilitare API sul progetto.

**Soluzione:**
- Verifica di avere il ruolo **"Project Editor"** o **"Owner"** sul progetto
- Chiedi al proprietario del progetto di concederti i permessi necessari

### 2. Project ID Errato
Il Project ID potrebbe non essere corretto o il progetto potrebbe non esistere.

**Soluzione:**
- Verifica il Project ID in Google Cloud Console
- Assicurati di essere nel progetto corretto

### 3. API Non Disponibile per il Progetto
Alcune API potrebbero non essere disponibili per tutti i tipi di progetto.

**Soluzione:**
- Usa la Console Web invece della CLI
- Verifica che il progetto sia attivo e la fatturazione sia abilitata (se richiesto)

## Soluzioni

### Soluzione 1: Usa la Console Web (Raccomandato)

1. Vai su [Google Cloud Console](https://console.cloud.google.com/)
2. Seleziona il progetto corretto (ID: `526374196058`)
3. Vai su **APIs & Services** → **Library**
4. Cerca "Google Calendar API"
5. Clicca su **Enable**

**Link diretto:**
- [Google Calendar API - Enable](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com?project=526374196058)

### Soluzione 2: Verifica Permessi

```bash
# Verifica i tuoi permessi sul progetto
gcloud projects get-iam-policy 526374196058 \
  --flatten="bindings[].members" \
  --filter="bindings.members:YOUR_EMAIL" \
  --format="table(bindings.role)"
```

Sostituisci `YOUR_EMAIL` con la tua email Google.

### Soluzione 3: Abilita Manualmente via Console

1. Accedi a [Google Cloud Console](https://console.cloud.google.com/)
2. Seleziona il progetto
3. Vai su **APIs & Services** → **Enabled APIs**
4. Clicca su **+ ENABLE APIS AND SERVICES**
5. Cerca "Calendar" e seleziona "Google Calendar API"
6. Clicca su **Enable**

### Soluzione 4: Usa un Account con Permessi Maggiori

Se non hai i permessi necessari:
1. Chiedi al proprietario del progetto di abilitare l'API
2. Oppure chiedi di essere aggiunto come "Project Editor" o "Owner"

## Verifica

Dopo aver abilitato l'API:

1. Vai su **APIs & Services** → **Enabled APIs**
2. Verifica che "Google Calendar API" sia nella lista
3. Attendi 1-2 minuti per la propagazione
4. Prova di nuovo il tool Calendar

## Alternative

Se continui ad avere problemi:

1. **Crea un nuovo progetto** con permessi completi
2. **Usa le credenziali OAuth** del nuovo progetto
3. **Aggiorna le variabili d'ambiente** con le nuove credenziali

## Riferimenti

- [Google Cloud IAM Documentation](https://cloud.google.com/iam/docs)
- [Google Calendar API Documentation](https://developers.google.com/calendar/api)
- [Enable APIs in Google Cloud Console](https://console.cloud.google.com/apis/library)

