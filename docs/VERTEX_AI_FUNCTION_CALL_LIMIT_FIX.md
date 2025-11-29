# Fix per il Limite di Function Calls di Vertex AI

## Problema

Quando l'assistente esegue molti tool calls in sequenza (es. 10 chiamate consecutive a `mcp_get_drive_file_content` per leggere file da Google Drive), Vertex AI restituisce un errore `400 INVALID_ARGUMENT` con il messaggio troncato "Please ensure that the number of function...".

Questo accade perché Vertex AI ha un limite sul numero di function calls che possono essere inclusi in una singola conversazione quando si genera la risposta finale.

## Causa

Il problema si verifica quando:
1. L'assistente esegue molti tool calls (es. 10 file da Google Drive)
2. Tutti i tool results vengono aggiunti come `function_response` nella conversazione
3. Vertex AI rifiuta la richiesta perché il numero totale di function calls supera il limite

## Soluzione Implementata

### 1. Configurazione del Limite

Aggiunta una nuova configurazione in `backend/app/core/config.py`:

```python
max_tool_results_per_response: int = 5  # Maximum number of tool results to pass to LLM when generating final response
```

Questo limite può essere configurato tramite variabile d'ambiente `MAX_TOOL_RESULTS_PER_RESPONSE`.

### 2. Limitazione dei Tool Results

Modificato `backend/app/agents/langgraph_app.py` per limitare il numero di tool results passati a Vertex AI quando genera la risposta finale:

- **Priorità**: I tool results vengono limitati dando priorità ai risultati di successo, poi agli errori, poi agli altri
- **Nota informativa**: Se i tool results vengono limitati, viene aggiunta una nota che informa l'utente che tutti i tool sono stati eseguiti correttamente, ma solo i primi N risultati sono stati inclusi nella risposta

### 3. Limitazione dei Tool Calls

Anche i `tool_calls` vengono limitati per corrispondere al numero di `function_responses` inclusi, evitando mismatch nella conversazione.

## Comportamento

### Prima del Fix

```
10 tool calls → 10 function_responses → Vertex AI rifiuta con 400 INVALID_ARGUMENT
```

### Dopo il Fix

```
10 tool calls → 5 function_responses (limitati) → Vertex AI accetta e genera risposta
+ Nota: "Sono stati eseguiti 10 tool in totale, ma solo i primi 5 risultati sono stati inclusi..."
```

## Configurazione

Per modificare il limite, aggiungi al tuo `.env`:

```bash
MAX_TOOL_RESULTS_PER_RESPONSE=5  # Default: 5
```

**Nota**: Un valore troppo basso potrebbe escludere risultati importanti. Un valore troppo alto potrebbe ancora causare errori con Vertex AI. Il valore di default (5) è stato scelto come compromesso tra completezza e compatibilità.

## Limitazioni

- I tool vengono comunque **tutti eseguiti** correttamente
- Solo i risultati passati a Vertex AI per la generazione della risposta sono limitati
- L'utente viene informato quando i risultati sono limitati
- La limitazione dà priorità ai risultati di successo rispetto agli errori

## Test

Per testare la soluzione:

1. Esegui una ricerca su Google Drive che restituisce molti file (es. > 5)
2. Verifica che tutti i tool vengano eseguiti correttamente
3. Verifica che la risposta finale venga generata senza errori `400 INVALID_ARGUMENT`
4. Verifica che venga mostrata una nota informativa se i risultati sono stati limitati

## Riferimenti

- Issue: Errore `400 INVALID_ARGUMENT` quando si eseguono molti tool calls consecutivi
- File modificati:
  - `backend/app/core/config.py` - Aggiunta configurazione `max_tool_results_per_response`
  - `backend/app/agents/langgraph_app.py` - Implementata limitazione dei tool results

