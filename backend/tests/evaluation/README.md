# Agent Evaluation System

Sistema di evaluation per testare e validare le performance dell'agent.

## Struttura

- `test_cases.py`: Definisce i test cases per vari scenari (calendar, email, web search, maps, memory, general)
- `run_evaluation.py`: Script per eseguire l'evaluation e generare report

## Utilizzo

### Eseguire tutti i test cases

```bash
cd backend
python scripts/run_evaluation.py
```

### Eseguire test cases per categoria

```bash
# Solo test calendar
python scripts/run_evaluation.py --category calendar

# Solo test email
python scripts/run_evaluation.py --category email

# Solo test web search
python scripts/run_evaluation.py --category web_search

# Solo test maps
python scripts/run_evaluation.py --category maps

# Solo test memory
python scripts/run_evaluation.py --category memory

# Solo test general
python scripts/run_evaluation.py --category general
```

### Eseguire test cases specifici

```bash
python scripts/run_evaluation.py --test-ids calendar_001 email_001 web_001
```

### Eseguire test in parallelo

```bash
python scripts/run_evaluation.py --parallel
```

### Personalizzare output

```bash
# JSON report personalizzato
python scripts/run_evaluation.py --output my_report.json

# Text report personalizzato
python scripts/run_evaluation.py --text-output my_report.txt

# HTML report (opzionale)
python scripts/run_evaluation.py --html-output my_report.html

# Tutti e tre i report
python scripts/run_evaluation.py --output report.json --text-output report.txt --html-output report.html
```

## Metriche di Evaluation

Il sistema calcola le seguenti metriche per ogni test case:

1. **Accuracy**: Percentuale di keywords attese trovate nella risposta
2. **Relevance**: La risposta ha la lunghezza minima richiesta
3. **Latency**: Tempo di risposta in secondi
4. **Tool Usage**: Percentuale di tool attesi che sono stati utilizzati
5. **Completeness**: La risposta è completa (non troncata)

## Report

Il sistema genera due tipi di report:

1. **JSON Report** (`evaluation_report.json`): Report strutturato in JSON per analisi programmatica
2. **Text Report** (`evaluation_report.txt`): Report leggibile con summary e dettagli

## Aggiungere Nuovi Test Cases

Per aggiungere nuovi test cases, modifica `test_cases.py`:

```python
NEW_TEST_CASES = [
    TestCase(
        id="new_001",
        name="Nuovo test",
        description="Descrizione del test",
        input_message="Messaggio di input",
        expected_tools=["tool1", "tool2"],  # Opzionale
        expected_keywords=["keyword1", "keyword2"],  # Opzionale
        expected_response_type="query_type",
        category="category_name",
        min_response_length=20,
        max_latency_seconds=30.0,
    ),
]

# Aggiungi a ALL_TEST_CASES
ALL_TEST_CASES = ALL_TEST_CASES + NEW_TEST_CASES
```

## Categorie di Test Cases

- **calendar**: Test per query calendario
- **email**: Test per query email
- **web_search**: Test per ricerca web
- **maps**: Test per Google Maps
- **memory**: Test per memoria e contesto
- **general**: Test per conversazione generale

## Esempio di Output

```
🧪 Agent Evaluation System
================================================================================

📋 Running all 15 test cases

1️⃣  Setting up database and session...
   ✅ Tenant: 123e4567-e89b-12d3-a456-426614174000
   ✅ Using existing evaluation session: 456e7890-e89b-12d3-a456-426614174001
   ✅ Using user: admin@example.com

2️⃣  Initializing evaluator...
   ✅ Evaluator initialized

3️⃣  Running evaluation (sequential)...
   This may take several minutes...

4️⃣  Generating reports...
   ✅ JSON report saved: evaluation_report.json
   ✅ Text report saved: evaluation_report.txt

================================================================================
EVALUATION SUMMARY
================================================================================
Total Tests: 15
Passed: 12 (80.0%)
Failed: 3 (20.0%)
Overall Accuracy: 85.3%
Average Latency: 2.45 seconds
Duration: 36.75 seconds
================================================================================
```

