# Esempi di Evaluation Results

Questo documento mostra esempi di risultati di evaluation per diversi scenari.

## Esempio 1: Test Case Semplice (PASS)

### Test Case
- **ID**: `general_001`
- **Nome**: Saluto semplice
- **Input**: "Ciao, come stai?"
- **Expected Keywords**: ["ciao", "stai"]

### Risultato
```json
{
    "test_case_id": "general_001",
    "test_case_name": "Saluto semplice",
    "passed": true,
    "metrics": {
        "accuracy": 1.0,
        "relevance": 1.0,
        "latency": 4.69,
        "tool_usage": 1.0,
        "completeness": 1.0
    },
    "actual_response": "Ciao! Sto bene, grazie. E tu, come stai?",
    "actual_tools_used": [],
    "latency_seconds": 4.69,
    "errors": [],
    "timestamp": "2025-11-17T18:23:26.196630"
}
```

### Analisi
- ✅ **Accuracy**: 100% - Entrambe le keywords ("ciao", "stai") sono state trovate nella risposta
- ✅ **Relevance**: 100% - La risposta è rilevante e ha la lunghezza minima richiesta
- ✅ **Latency**: 4.69s - Sotto il limite di 30s
- ✅ **Tool Usage**: 100% - Nessun tool richiesto, risposta diretta appropriata
- ✅ **Completeness**: 100% - Risposta completa

**Status**: ✅ PASS

---

## Esempio 2: Test Case con Latenza Elevata (FAIL)

### Test Case
- **ID**: `general_002`
- **Nome**: Domanda informativa
- **Input**: "Cos'è Python?"
- **Expected Keywords**: ["Python"]
- **Max Latency**: 30.0s

### Risultato
```json
{
    "test_case_id": "general_002",
    "test_case_name": "Domanda informativa",
    "passed": false,
    "metrics": {
        "accuracy": 1.0,
        "relevance": 1.0,
        "latency": 39.13,
        "tool_usage": 1.0,
        "completeness": 1.0
    },
    "actual_response": "Python è un linguaggio di programmazione ad alto livello, interpretato e di uso generale, noto per la sua sintassi chiara e leggibile...",
    "actual_tools_used": [],
    "latency_seconds": 39.13,
    "errors": [],
    "timestamp": "2025-11-17T18:25:00.439860"
}
```

### Analisi
- ✅ **Accuracy**: 100% - Keyword "Python" trovata
- ✅ **Relevance**: 100% - Risposta rilevante e completa
- ❌ **Latency**: 39.13s - **SUPERA il limite di 30s**
- ✅ **Tool Usage**: 100% - Nessun tool richiesto
- ✅ **Completeness**: 100% - Risposta completa

**Status**: ❌ FAIL (Latenza troppo elevata)

**Nota**: Questo esempio dimostra come il sistema di evaluation rileva problemi di performance anche quando la risposta è corretta.

---

## Esempio 3: Test Case con Tool Usage (PASS)

### Test Case
- **ID**: `calendar_001`
- **Nome**: Query eventi oggi
- **Input**: "Quali eventi ho oggi?"
- **Expected Tools**: ["get_calendar_events"]
- **Expected Keywords**: ["evento", "oggi", "calendario"]

### Risultato (Esempio)
```json
{
    "test_case_id": "calendar_001",
    "test_case_name": "Query eventi oggi",
    "passed": true,
    "metrics": {
        "accuracy": 1.0,
        "relevance": 1.0,
        "latency": 2.5,
        "tool_usage": 1.0,
        "completeness": 1.0
    },
    "actual_response": "Oggi hai 3 eventi in calendario: riunione alle 10:00, pranzo alle 13:00, e call alle 15:00.",
    "actual_tools_used": ["get_calendar_events"],
    "latency_seconds": 2.5,
    "errors": [],
    "timestamp": "2025-11-17T18:30:00.000000"
}
```

### Analisi
- ✅ **Accuracy**: 100% - Tutte le keywords trovate
- ✅ **Relevance**: 100% - Risposta rilevante
- ✅ **Latency**: 2.5s - Eccellente
- ✅ **Tool Usage**: 100% - Tool atteso utilizzato correttamente
- ✅ **Completeness**: 100% - Risposta completa

**Status**: ✅ PASS

---

## Esempio 4: Test Case con Accuracy Parziale (FAIL)

### Test Case
- **ID**: `web_001`
- **Nome**: Ricerca web semplice
- **Input**: "Cerca informazioni su Python 3.13"
- **Expected Keywords**: ["Python", "3.13"]

### Risultato (Esempio)
```json
{
    "test_case_id": "web_001",
    "test_case_name": "Ricerca web semplice",
    "passed": false,
    "metrics": {
        "accuracy": 0.5,
        "relevance": 1.0,
        "latency": 5.2,
        "tool_usage": 1.0,
        "completeness": 1.0
    },
    "actual_response": "Python è un linguaggio di programmazione popolare. Ecco alcune informazioni generali...",
    "actual_tools_used": ["web_search"],
    "latency_seconds": 5.2,
    "errors": [],
    "timestamp": "2025-11-17T18:35:00.000000"
}
```

### Analisi
- ⚠️ **Accuracy**: 50% - Solo "Python" trovato, "3.13" mancante
- ✅ **Relevance**: 100% - Risposta rilevante
- ✅ **Latency**: 5.2s - Accettabile
- ✅ **Tool Usage**: 100% - Tool utilizzato
- ✅ **Completeness**: 100% - Risposta completa

**Status**: ❌ FAIL (Accuracy insufficiente - keyword "3.13" non trovata)

---

## Report Completo di Esempio

### Evaluation Report Summary
```json
{
    "total_tests": 5,
    "passed_tests": 3,
    "failed_tests": 2,
    "overall_accuracy": 0.9,
    "average_latency": 12.5,
    "tool_usage_stats": {
        "get_calendar_events": 1,
        "web_search": 1
    },
    "timestamp": "2025-11-17T18:40:00.000000",
    "duration_seconds": 62.5
}
```

### Text Report Example
```
================================================================================
AGENT EVALUATION REPORT
================================================================================
Timestamp: 2025-11-17T18:40:00.000000
Duration: 62.5 seconds

SUMMARY
--------------------------------------------------------------------------------
Total Tests: 5
Passed: 3 (60.0%)
Failed: 2 (40.0%)
Overall Accuracy: 90.00%
Average Latency: 12.5 seconds

TOOL USAGE STATISTICS
--------------------------------------------------------------------------------
  get_calendar_events: 1
  web_search: 1

DETAILED RESULTS
--------------------------------------------------------------------------------

✅ PASS - Saluto semplice (general_001)
  Latency: 4.69s
  Accuracy: 100.00%
  Relevance: 100.00%
  Tool Usage: 100.00%
  Tools Used: None

❌ FAIL - Domanda informativa (general_002)
  Latency: 39.13s
  Accuracy: 100.00%
  Relevance: 100.00%
  Tool Usage: 100.00%
  Tools Used: None
  Response Preview: Python è un linguaggio di programmazione ad alto livello...

✅ PASS - Query eventi oggi (calendar_001)
  Latency: 2.5s
  Accuracy: 100.00%
  Relevance: 100.00%
  Tool Usage: 100.00%
  Tools Used: get_calendar_events

❌ FAIL - Ricerca web semplice (web_001)
  Latency: 5.2s
  Accuracy: 50.00%
  Relevance: 100.00%
  Tool Usage: 100.00%
  Tools Used: web_search
  Response Preview: Python è un linguaggio di programmazione popolare...

✅ PASS - Query email non lette (email_001)
  Latency: 3.1s
  Accuracy: 100.00%
  Relevance: 100.00%
  Tool Usage: 100.00%
  Tools Used: get_emails

================================================================================
```

## Interpretazione dei Risultati

### Metriche Chiave

1. **Accuracy**: Percentuale di keywords attese trovate nella risposta
   - 1.0 (100%) = Tutte le keywords trovate
   - 0.5 (50%) = Metà delle keywords trovate
   - 0.0 (0%) = Nessuna keyword trovata

2. **Relevance**: La risposta è rilevante e ha la lunghezza minima
   - 1.0 = Risposta rilevante e completa
   - 0.0 = Risposta troppo corta o non rilevante

3. **Latency**: Tempo di risposta in secondi
   - Deve essere < `max_latency_seconds` del test case
   - Tipicamente < 30s per test cases generali

4. **Tool Usage**: Percentuale di tool attesi utilizzati
   - 1.0 = Tutti i tool attesi utilizzati
   - 0.5 = Metà dei tool attesi utilizzati
   - 0.0 = Nessun tool utilizzato (quando richiesto)

5. **Completeness**: La risposta è completa
   - 1.0 = Risposta completa (>= min_response_length)
   - 0.0 = Risposta incompleta

### Criteri di Pass/Fail

Un test case **PASSA** se:
- ✅ Nessun errore durante l'esecuzione
- ✅ Latency < max_latency_seconds
- ✅ Relevance >= 0.5
- ✅ Accuracy >= 0.5 (se keywords attese)
- ✅ Tool Usage >= 0.5 (se tools attesi)

Un test case **FALLISCE** se:
- ❌ Errori durante l'esecuzione
- ❌ Latency > max_latency_seconds
- ❌ Relevance < 0.5
- ❌ Accuracy < 0.5 (se keywords attese)
- ❌ Tool Usage < 0.5 (se tools attesi)

