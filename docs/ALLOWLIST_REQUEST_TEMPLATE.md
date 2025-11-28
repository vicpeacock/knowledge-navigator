# Template Richiesta Allowlist BLOCK_NONE - Pronto da Copiare

## Come Trovare il Tuo Google Cloud Project ID

1. **Da Google Cloud Console**:
   - Vai su https://console.cloud.google.com/
   - Il Project ID è visibile nella barra superiore (accanto al nome del progetto)
   - Oppure vai su "IAM & Admin" > "Settings" per vedere il Project ID completo

2. **Dalla tua Gemini API Key**:
   - Se hai già una API key, il Project ID potrebbe essere associato
   - Controlla le impostazioni della API key nella console

## Template Email/Ticket (Copia e Incolla)

**Oggetto**: Richiesta Allowlist per BLOCK_NONE Safety Settings - Gemini API

---

**Corpo del Messaggio**:

```
Gentile Team Google AI/Vertex AI,

Desidero richiedere l'accesso all'allowlist per utilizzare BLOCK_NONE nei safety settings 
di Gemini API (Generative AI).

**Caso d'Uso Specifico:**
Sto sviluppando un assistente AI personale ("Knowledge Navigator") che utilizza Gemini API 
per sintetizzare risultati provenienti da tool trusted e verificati. L'applicazione integra:

- Google Calendar API (per recuperare eventi del calendario)
- Gmail API (per recuperare email)
- Google Custom Search API (per ricerche web)

**Problema Riscontrato:**
Anche configurando i safety settings con BLOCK_NONE (threshold=4), Gemini continua a bloccare 
le risposte con finish_reason=1 (SAFETY), nonostante tutti i safety ratings sull'output 
risultino NEGLIGIBLE e Blocked=False.

Questo indica che il blocco avviene a livello infrastrutturale/policy, non a livello di 
contenuto. I log mostrano:

- Safety ratings sull'output: tutti NEGLIGIBLE (HARASSMENT, HATE_SPEECH, SEXUALLY_EXPLICIT, DANGEROUS_CONTENT)
- Prompt feedback: vuoto (nessun blocco sull'input)
- Finish reason: 1 (SAFETY) nonostante i rating non bloccanti

**Perché ho bisogno di BLOCK_NONE:**
1. I risultati dei tool provengono da fonti trusted (API Google ufficiali)
2. I contenuti sono già verificati e sicuri (eventi calendario, email personali, risultati ricerca)
3. Il blocco impedisce la sintesi di risposte legittime anche per query semplici come "Che giorno è oggi?"
4. L'uso di BLOCK_ONLY_HIGH non risolve il problema (il blocco persiste)

**Dettagli Tecnici:**
- Modello utilizzato: gemini-2.5-pro
- API: Google Generative AI (genai)
- Configurazione attuale: BLOCK_NONE (threshold=4) per tutte le categorie
- Problema: Blocco persistente anche con rating NEGLIGIBLE

**Informazioni Account:**
- Google Cloud Project ID: [INSERIRE IL TUO PROJECT ID QUI]
- Email account: [INSERIRE LA TUA EMAIL QUI]
- Tipo account: [Personal/Enterprise]

**Esempio di Query che viene Bloccata:**
- Query utente: "Che giorno è oggi?"
- Tool eseguito: customsearch_search (risultati trusted da Google Custom Search)
- Risultato: finish_reason=1 nonostante safety ratings tutti NEGLIGIBLE

Sono disponibile a fornire log dettagliati, screenshot, o esempi specifici se necessario.

Grazie per la considerazione.

Cordiali saluti,
[Il tuo nome]
```

## Dove Inviare la Richiesta

### Opzione 1: Google Cloud Console Support (CONSIGLIATO)
1. Vai su https://console.cloud.google.com/
2. Seleziona il tuo progetto
3. Vai su "Support" o "Help & Support"
4. Crea un nuovo ticket
5. Categoria: "Technical Support" > "API" > "Generative AI" o "Vertex AI"
6. Incolla il template sopra

### Opzione 2: Google AI Studio
1. Vai su https://aistudio.google.com/
2. Cerca "Support" o "Help"
3. Invia una richiesta con il template sopra

### Opzione 3: Forum Google AI
1. Vai su https://discuss.ai.google.dev/
2. Crea un nuovo post con il template sopra

## Note Importanti

- **Requisiti**: Potrebbe essere necessario un account con fatturazione mensile tramite fattura
- **Tempi**: L'approvazione può richiedere diversi giorni o settimane
- **Non Garantito**: Google potrebbe non approvare tutte le richieste

## Dopo l'Invio

Dopo aver inviato la richiesta, monitora i log del backend. Quando l'allowlist sarà attiva:
- Non vedrai più "BLOCK_NONE requires allowlist approval" nei log
- Gemini risponderà normalmente anche con BLOCK_NONE configurato
- I blocchi con finish_reason=1 dovrebbero scomparire per contenuti legittimi

