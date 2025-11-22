# Come Verificare le API Google Workspace Abilitate

## Metodo 1: Console Web (Più Semplice)

### Verifica Tutte le API in una Volta
1. Vai su: https://console.cloud.google.com/apis/library?project=526374196058
2. Nella barra di ricerca, cerca "Google" per vedere tutte le API Google
3. Le API abilitate mostrano "API enabled" sotto il nome

### Verifica API Specifiche
Clicca su ogni link per verificare lo stato:

- [Google Drive API](https://console.cloud.google.com/apis/library/drive.googleapis.com?project=526374196058)
- [Gmail API](https://console.cloud.google.com/apis/library/gmail.googleapis.com?project=526374196058)
- [Google Calendar API](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com?project=526374196058)
- [Google Sheets API](https://console.cloud.google.com/apis/library/sheets.googleapis.com?project=526374196058)
- [Google Docs API](https://console.cloud.google.com/apis/library/docs.googleapis.com?project=526374196058)
- [Google Slides API](https://console.cloud.google.com/apis/library/slides.googleapis.com?project=526374196058)

Se vedi il pulsante "ENABLE", l'API non è abilitata. Se vedi "MANAGE", l'API è già abilitata.

## Metodo 2: Script Bash

Se hai `gcloud` CLI installato:

```bash
cd "/Users/pallotta/Personal AI Assistant"
./check-google-apis.sh 526374196058
```

## Metodo 3: gcloud CLI Diretto

```bash
# Lista tutte le API abilitate
gcloud services list --enabled --project=526374196058

# Verifica una specifica API
gcloud services list --enabled --project=526374196058 | grep drive.googleapis.com
```

## Metodo 4: Verifica Rapida via Browser

Apri questi link e verifica se vedi "MANAGE" (abilitata) o "ENABLE" (non abilitata):

1. **Google Drive API**: https://console.cloud.google.com/apis/library/drive.googleapis.com?project=526374196058
   - ✅ Se vedi "MANAGE" → Abilitata
   - ❌ Se vedi "ENABLE" → Non abilitata

2. **Gmail API**: https://console.cloud.google.com/apis/library/gmail.googleapis.com?project=526374196058
   - ✅ Se vedi "MANAGE" → Abilitata
   - ❌ Se vedi "ENABLE" → Non abilitata

3. **Google Calendar API**: https://console.cloud.google.com/apis/library/calendar-json.googleapis.com?project=526374196058
   - ✅ Se vedi "MANAGE" → Abilitata
   - ❌ Se vedi "ENABLE" → Non abilitata

4. **Google Sheets API**: https://console.cloud.google.com/apis/library/sheets.googleapis.com?project=526374196058
   - ✅ Se vedi "MANAGE" → Abilitata
   - ❌ Se vedi "ENABLE" → Non abilitata

5. **Google Docs API**: https://console.cloud.google.com/apis/library/docs.googleapis.com?project=526374196058
   - ✅ Se vedi "MANAGE" → Abilitata
   - ❌ Se vedi "ENABLE" → Non abilitata

6. **Google Slides API**: https://console.cloud.google.com/apis/library/slides.googleapis.com?project=526374196058
   - ✅ Se vedi "MANAGE" → Abilitata
   - ❌ Se vedi "ENABLE" → Non abilitata

## Checklist Rapida

- [ ] Google Drive API
- [ ] Gmail API
- [ ] Google Calendar API
- [ ] Google Sheets API (opzionale)
- [ ] Google Docs API (opzionale)
- [ ] Google Slides API (opzionale)

## Se Alcune API Non Sono Abilitate

Usa i link diretti per abilitarle:

- [Abilita Google Drive API](https://console.cloud.google.com/flows/enableapi?apiid=drive.googleapis.com&project=526374196058)
- [Abilita Gmail API](https://console.cloud.google.com/flows/enableapi?apiid=gmail.googleapis.com&project=526374196058)
- [Abilita Google Calendar API](https://console.cloud.google.com/flows/enableapi?apiid=calendar-json.googleapis.com&project=526374196058)
- [Abilita Google Sheets API](https://console.cloud.google.com/flows/enableapi?apiid=sheets.googleapis.com&project=526374196058)
- [Abilita Google Docs API](https://console.cloud.google.com/flows/enableapi?apiid=docs.googleapis.com&project=526374196058)
- [Abilita Google Slides API](https://console.cloud.google.com/flows/enableapi?apiid=slides.googleapis.com&project=526374196058)

