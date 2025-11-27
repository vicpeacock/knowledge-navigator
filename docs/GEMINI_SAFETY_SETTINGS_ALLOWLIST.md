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

3. **Informazioni da Includere nella Richiesta**:
   ```
   Oggetto: Richiesta Allowlist per BLOCK_NONE Safety Settings
   
   Desidero richiedere l'accesso a BLOCK_NONE nei safety settings di Gemini API.
   
   Caso d'uso:
   - Sto sviluppando un assistente AI che usa Gemini per sintetizzare risultati da tool trusted
   - I tool sono interni e trusted (calendario Google, Gmail, ricerca web)
   - Ho bisogno di BLOCK_NONE per evitare che i safety filters blocchino risposte legittime
   - I risultati dei tool sono già verificati e trusted
   
   Project ID: [il tuo Google Cloud Project ID]
   API Key: [la tua Gemini API Key - opzionale]
   ```

### Opzione 2: Google Cloud Console Support

1. **Vai su Google Cloud Console**:
   - Visita: https://console.cloud.google.com/
   - Seleziona il tuo progetto

2. **Apri il Supporto**:
   - Vai su "Support" nel menu
   - Crea un nuovo ticket di supporto
   - Seleziona "Technical Support" > "API" > "Generative AI"

3. **Richiedi l'Allowlist**:
   - Spiega che hai bisogno di `BLOCK_NONE` per sintetizzare risultati di tool trusted
   - Fornisci il tuo Project ID e API Key

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
- **Alternativa Consigliata**: Per la maggior parte dei casi d'uso, `BLOCK_ONLY_HIGH` dovrebbe essere sufficiente

## Riferimenti

- [Google AI Studio](https://aistudio.google.com/)
- [Google Cloud Console](https://console.cloud.google.com/)
- [Google AI Forum](https://discuss.ai.google.dev/)
- [Gemini API Documentation](https://ai.google.dev/docs)

