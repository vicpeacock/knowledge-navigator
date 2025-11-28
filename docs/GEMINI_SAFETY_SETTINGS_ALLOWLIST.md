# Come Richiedere l'Allowlist per BLOCK_NONE nei Safety Settings di Gemini API

## Panoramica

Per usare `BLOCK_NONE` nei safety settings di Gemini API (che disabilita completamente i filtri di sicurezza), è necessario essere aggiunti a un'allowlist da Google. Questo è necessario perché Google limita l'uso di `BLOCK_NONE` per motivi di sicurezza.

## Opzioni per Richiedere l'Allowlist

### Opzione 1: Google AI Studio / Vertex AI Support

1. **Vai su Google AI Studio**:
   - Visita: https://aistudio.google.com/
   - Accedi con il tuo account Google

2. **Contatta il Supporto**:
   - Cerca "Support" o "Help" nella console
   - Invia una richiesta spiegando che hai bisogno di `BLOCK_NONE` per sintetizzare risultati di tool trusted
   - Spiega il caso d'uso: sintesi di risultati da tool interni (calendario, email, ricerca) che sono già trusted

3. **Template Completo per la Richiesta**:
   
   **Oggetto**: Richiesta Allowlist per BLOCK_NONE Safety Settings - Gemini API
   
   **Corpo della Richiesta**:
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
   - Google Cloud Project ID: [INSERIRE IL TUO PROJECT ID]
   - Email account: [INSERIRE LA TUA EMAIL]
   - Tipo account: [Personal/Enterprise]
   
   **Esempio di Query che viene Bloccata:**
   - Query utente: "Che giorno è oggi?"
   - Tool eseguito: customsearch_search (risultati trusted da Google Custom Search)
   - Risultato: finish_reason=1 nonostante safety ratings tutti NEGLIGIBLE
   
   Potrei fornire log dettagliati e esempi specifici se necessario.
   
   Grazie per la considerazione.
   
   Cordiali saluti,
   [Il tuo nome]
   ```

### Opzione 2: Google Cloud Console Support (CONSIGLIATO)

1. **Vai su Google Cloud Console**:
   - Visita: https://console.cloud.google.com/
   - Seleziona il tuo progetto

2. **Apri il Supporto**:
   - Vai su "Support" nel menu (o "Help & Support")
   - Crea un nuovo ticket di supporto
   - Seleziona "Technical Support" > "API" > "Generative AI" o "Vertex AI"
   - **Nota**: Se non hai un piano di supporto, potresti dover passare a un account con fatturazione mensile

3. **Richiedi l'Allowlist**:
   - Usa il template sopra come base
   - Includi i dettagli del problema specifico (finish_reason=1 con rating NEGLIGIBLE)
   - Fornisci il tuo Project ID
   - **Importante**: Secondo la documentazione Google, potrebbe essere necessario un account con fatturazione mensile tramite fattura per ottenere l'allowlist

### Opzione 3: Forum Google AI

1. **Vai al Forum Google AI**:
   - Visita: https://discuss.ai.google.dev/
   - Cerca discussioni esistenti su "BLOCK_NONE allowlist"
   - Se non trovi nulla, crea un nuovo post chiedendo come richiedere l'allowlist

### Opzione 4: Contatto Diretto (per Account Enterprise)

Se hai un account Google Cloud Enterprise:
- Contatta il tuo account manager Google
- Chiedi informazioni sull'allowlist per `BLOCK_NONE` nei safety settings

## Alternative se l'Allowlist Non è Disponibile

Se non riesci a ottenere l'allowlist, puoi:

1. **Usare BLOCK_ONLY_HIGH** (già implementato):
   - È il livello più permissivo disponibile senza allowlist
   - Blocca solo contenuti con probabilità ALTA di essere dannosi
   - Dovrebbe essere sufficiente per la maggior parte dei casi d'uso

2. **Migliorare i Prompt**:
   - Usa linguaggio neutro e fattuale
   - Evita termini che potrebbero triggerare i safety filters
   - Formatta i risultati dei tool in modo pulito e strutturato

3. **Pre-formattare le Risposte**:
   - Per casi semplici (es: "nessun evento trovato"), genera direttamente la risposta senza chiamare Gemini
   - Usa Gemini solo per sintetizzare risultati complessi

## Verifica dello Stato dell'Allowlist

Dopo aver inviato la richiesta, puoi verificare se `BLOCK_NONE` funziona:

1. **Controlla i Log**:
   - Se vedi "BLOCK_NONE requires allowlist approval" nei log, l'allowlist non è ancora attiva
   - Se non vedi errori e Gemini risponde normalmente, l'allowlist potrebbe essere attiva

2. **Test Diretto**:
   - Prova a chiamare Gemini con `disable_safety_filters=True`
   - Se la risposta viene generata senza blocchi, l'allowlist è attiva

## Note Importanti

- **Tempi di Approvazione**: L'approvazione dell'allowlist può richiedere diversi giorni o settimane
- **Non Garantito**: Google potrebbe non approvare tutte le richieste
- **Requisiti Account**: Secondo la documentazione Google, potrebbe essere necessario un account con fatturazione mensile tramite fattura per ottenere l'allowlist
- **Alternativa Consigliata**: Per la maggior parte dei casi d'uso, `BLOCK_ONLY_HIGH` dovrebbe essere sufficiente, ma nel nostro caso non risolve il problema

## Evidenze del Problema (per la Richiesta)

Per supportare la tua richiesta, puoi includere queste evidenze:

1. **Log che mostrano il problema**:
   - Safety ratings sull'output: tutti NEGLIGIBLE
   - Finish reason: 1 (SAFETY) nonostante rating non bloccanti
   - Prompt feedback: vuoto (nessun blocco sull'input)

2. **Esempio di query bloccata**:
   - Query: "Che giorno è oggi?"
   - Tool eseguito: customsearch_search (risultati trusted)
   - Risultato: Bloccato anche con BLOCK_NONE configurato

3. **Configurazione attuale**:
   - Safety settings: BLOCK_NONE (threshold=4) per tutte le categorie
   - Modello: gemini-2.5-pro
   - Problema persiste anche con BLOCK_ONLY_HIGH

## Riferimenti

- [Google AI Studio](https://aistudio.google.com/)
- [Google Cloud Console](https://console.cloud.google.com/)
- [Google AI Forum](https://discuss.ai.google.dev/)
- [Gemini API Documentation](https://ai.google.dev/docs)

