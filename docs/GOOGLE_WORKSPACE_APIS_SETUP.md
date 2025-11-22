# Abilitazione API Google Workspace in Google Cloud Console

Questa guida spiega come abilitare tutte le API Google Workspace necessarie per il Google Workspace MCP Server.

## API Richieste

Il Google Workspace MCP Server richiede le seguenti API:

### API Principali (Obbligatorie)
1. **Google Drive API** - Per accesso ai file di Drive
2. **Gmail API** - Per accesso alle email
3. **Google Calendar API** - Per accesso al calendario

### API Opzionali (se usi i tool corrispondenti)
4. **Google Sheets API** - Per fogli di calcolo
5. **Google Docs API** - Per documenti Google Docs
6. **Google Slides API** - Per presentazioni
7. **Google Contacts API** - Per contatti

## Metodo 1: Abilitazione tramite Console Web (Raccomandato)

### Passo 1: Accedi a Google Cloud Console
1. Vai su [Google Cloud Console](https://console.cloud.google.com/)
2. Seleziona il progetto corretto (ID: `526374196058` o il tuo progetto)

### Passo 2: Abilita le API una per una

#### Google Drive API
- Link diretto: https://console.cloud.google.com/flows/enableapi?apiid=drive.googleapis.com
- Oppure: **APIs & Services** → **Library** → Cerca "Google Drive API" → **Enable**

#### Gmail API
- Link diretto: https://console.cloud.google.com/flows/enableapi?apiid=gmail.googleapis.com
- Oppure: **APIs & Services** → **Library** → Cerca "Gmail API" → **Enable**

#### Google Calendar API
- Link diretto: https://console.cloud.google.com/flows/enableapi?apiid=calendar-json.googleapis.com
- Oppure: **APIs & Services** → **Library** → Cerca "Google Calendar API" → **Enable**
- **Nota**: Il nome del servizio è `calendar-json.googleapis.com` (non `calendar.googleapis.com`)

#### Google Sheets API (opzionale)
- Link diretto: https://console.cloud.google.com/flows/enableapi?apiid=sheets.googleapis.com
- Oppure: **APIs & Services** → **Library** → Cerca "Google Sheets API" → **Enable**

#### Google Docs API (opzionale)
- Link diretto: https://console.cloud.google.com/flows/enableapi?apiid=docs.googleapis.com
- Oppure: **APIs & Services** → **Library** → Cerca "Google Docs API" → **Enable**

#### Google Slides API (opzionale)
- Link diretto: https://console.cloud.google.com/flows/enableapi?apiid=slides.googleapis.com
- Oppure: **APIs & Services** → **Library** → Cerca "Google Slides API" → **Enable**

### Passo 3: Verifica
1. Vai su **APIs & Services** → **Enabled APIs**
2. Verifica che tutte le API necessarie siano elencate come "Enabled"

## Metodo 2: Abilitazione tramite gcloud CLI

Se preferisci usare la command line, puoi abilitare tutte le API con un singolo comando:

```bash
# Imposta il progetto
gcloud config set project YOUR_PROJECT_ID

# Abilita tutte le API necessarie
gcloud services enable \
  drive.googleapis.com \
  gmail.googleapis.com \
  calendar-json.googleapis.com \
  sheets.googleapis.com \
  docs.googleapis.com \
  slides.googleapis.com
```

**Nota**: Il nome corretto per Calendar API è `calendar-json.googleapis.com` (non `calendar.googleapis.com`)

### Verifica con gcloud
```bash
# Lista tutte le API abilitate
gcloud services list --enabled

# Verifica una specifica API
gcloud services list --enabled --filter="name:drive.googleapis.com"
```

## Metodo 3: Abilitazione Rapida (Tutte le API in una volta)

### Link Combinato (Console Web)
Puoi aprire tutti i link in nuove tab e abilitare tutte le API rapidamente:

1. [Google Drive API](https://console.cloud.google.com/flows/enableapi?apiid=drive.googleapis.com)
2. [Gmail API](https://console.cloud.google.com/flows/enableapi?apiid=gmail.googleapis.com)
3. [Google Calendar API](https://console.cloud.google.com/flows/enableapi?apiid=calendar-json.googleapis.com)
4. [Google Sheets API](https://console.cloud.google.com/flows/enableapi?apiid=sheets.googleapis.com)
5. [Google Docs API](https://console.cloud.google.com/flows/enableapi?apiid=docs.googleapis.com)
6. [Google Slides API](https://console.cloud.google.com/flows/enableapi?apiid=slides.googleapis.com)

### Script Bash per Abilitazione Automatica
Crea un file `enable-google-apis.sh`:

```bash
#!/bin/bash

PROJECT_ID="526374196058"  # Sostituisci con il tuo Project ID

echo "Abilitazione API Google Workspace per progetto: $PROJECT_ID"

APIS=(
  "drive.googleapis.com"
  "gmail.googleapis.com"
  "calendar-json.googleapis.com"  # Nome corretto per Calendar API
  "sheets.googleapis.com"
  "docs.googleapis.com"
  "slides.googleapis.com"
)

for api in "${APIS[@]}"; do
  echo "Abilitazione $api..."
  gcloud services enable "$api" --project="$PROJECT_ID"
done

echo "✅ Tutte le API sono state abilitate!"
echo "Verifica con: gcloud services list --enabled --project=$PROJECT_ID"
```

Esegui lo script:
```bash
chmod +x enable-google-apis.sh
./enable-google-apis.sh
```

## Verifica Finale

Dopo aver abilitato le API, attendi 1-2 minuti per la propagazione, poi verifica:

1. **Test tramite MCP Server**: Prova a chiamare un tool Drive/Gmail/Calendar
2. **Verifica in Console**: **APIs & Services** → **Enabled APIs** → Dovresti vedere tutte le API abilitate
3. **Controlla i Log**: Se vedi ancora errori "API not enabled", verifica che il Project ID sia corretto

## Troubleshooting

### Errore: "API not enabled"
- Verifica che il Project ID sia corretto (controlla in `docker-compose.yml` o variabili d'ambiente)
- Attendi 1-2 minuti dopo l'abilitazione
- Verifica che le credenziali OAuth siano associate al progetto corretto

### Errore: "Permission denied"
- Assicurati di avere i permessi "Project Editor" o "Owner" sul progetto
- Verifica che il progetto sia attivo e fatturazione abilitata (se richiesto)

### Errore: "Quota exceeded"
- Alcune API hanno limiti di quota giornaliera
- Verifica in **APIs & Services** → **Quotas** se ci sono limiti raggiunti

## Note Importanti

1. **Propagazione**: Le modifiche alle API possono richiedere 1-2 minuti per propagarsi
2. **Fatturazione**: Alcune API potrebbero richiedere fatturazione abilitata (anche se spesso c'è un tier gratuito)
3. **Permessi**: Assicurati che l'utente OAuth abbia i permessi necessari per accedere alle risorse
4. **Project ID**: Verifica sempre che il Project ID nelle credenziali OAuth corrisponda al progetto dove hai abilitato le API

## Riferimenti

- [Google Cloud Console](https://console.cloud.google.com/)
- [Google Workspace MCP Server Documentation](https://github.com/taylorwilsdon/google_workspace_mcp)
- [Google API Explorer](https://developers.google.com/apis-explorer)

