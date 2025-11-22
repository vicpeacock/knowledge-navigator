# Architettura LLM - Knowledge Navigator

## Panoramica

Il sistema Knowledge Navigator utilizza **tre tipi di LLM** per diversi scopi:

### 1. **LLM Principale (Main LLM)** - Chat Interattiva
- **Scopo**: Gestisce le conversazioni interattive con l'utente
- **Configurazione**: 
  - Ollama: `ollama_base_url`, `ollama_model`
  - Gemini: `gemini_api_key`, `gemini_model`
- **Default**: 
  - Ollama: `http://localhost:11434`, `gpt-oss:20b`
  - Gemini: `gemini-2.5-flash`
- **Uso**: 
  - Risposte alle richieste dell'utente
  - Generazione di risposte finali
  - Tool calling durante le conversazioni
- **Tool di Ricerca Web**:
  - **Ollama**: Usa `web_search` (richiede `OLLAMA_API_KEY`)
  - **Gemini**: Usa `customsearch_search` (richiede `GOOGLE_PSE_API_KEY` e `GOOGLE_PSE_CX`)

### 2. **Planner LLM** - Pianificazione delle Azioni
- **Scopo**: Analizza le richieste dell'utente e determina se serve un piano con tool
- **Configurazione**: `ollama_planner_base_url`, `ollama_planner_model`
- **Default**: Usa lo stesso LLM principale (Ollama)
- **Uso**:
  - Analisi delle richieste per determinare se servono tool
  - Creazione di piani di azione con step sequenziali
  - Decidere quali tool chiamare e in che ordine

**Nota**: Il planner dovrebbe usare lo stesso LLM principale per garantire coerenza. Se si vuole un planner più leggero, si può configurare esplicitamente.

### 3. **Background LLM** - Task in Background
- **Scopo**: Esegue task asincroni che non richiedono interazione immediata
- **Configurazione**: `ollama_background_base_url`, `ollama_background_model`, `use_llama_cpp_background`
- **Default**: llama.cpp (`http://127.0.0.1:11435`, `Phi-3-mini-4k-instruct-q4`)
- **Uso**:
  - Analisi di email in background
  - Controllo del calendario
  - Task di apprendimento automatico
  - Controllo di integrità semantica

**Nota**: Il background LLM può essere più leggero perché non richiede risposte immediate.

## Logica di Fallback

### Planner LLM
1. Se `ollama_planner_base_url` è configurato → usa quello
2. Altrimenti → usa `ollama_base_url` (LLM principale)

**Ragionamento**: Il planner è parte del flusso principale, quindi dovrebbe usare lo stesso LLM per coerenza.

### Background LLM
1. Se `use_llama_cpp_background = True` → usa llama.cpp (`ollama_background_base_url`)
2. Altrimenti → usa Ollama (`ollama_background_base_url`)

## Configurazione Consigliata

### Setup Standard (Ollama per tutto)
```python
# Main LLM: Ollama
ollama_base_url = "http://localhost:11434"
ollama_model = "gpt-oss:20b"

# Planner: stesso del main (default)
ollama_planner_base_url = None  # Usa main
ollama_planner_model = None     # Usa main

# Background: Ollama (più leggero)
ollama_background_base_url = "http://localhost:11434"
ollama_background_model = "phi3:mini"  # Modello più leggero
use_llama_cpp_background = False
```

### Setup Ottimizzato (llama.cpp per background)
```python
# Main LLM: Ollama (potente)
ollama_base_url = "http://localhost:11434"
ollama_model = "gpt-oss:20b"

# Planner: stesso del main
ollama_planner_base_url = None
ollama_planner_model = None

# Background: llama.cpp (veloce e leggero)
ollama_background_base_url = "http://127.0.0.1:11435"
ollama_background_model = "Phi-3-mini-4k-instruct-q4"
use_llama_cpp_background = True
```

### Setup Avanzato (Planner dedicato)
```python
# Main LLM: Ollama
ollama_base_url = "http://localhost:11434"
ollama_model = "gpt-oss:20b"

# Planner: modello più leggero per risparmiare risorse
ollama_planner_base_url = "http://localhost:11434"
ollama_planner_model = "phi3:mini"

# Background: llama.cpp
ollama_background_base_url = "http://127.0.0.1:11435"
ollama_background_model = "Phi-3-mini-4k-instruct-q4"
use_llama_cpp_background = True
```

## Note Importanti

1. **Coerenza del Planner**: Il planner dovrebbe idealmente usare lo stesso LLM principale per garantire che capisca correttamente le capacità e i tool disponibili.

2. **Performance**: Se il planner è troppo lento, si può configurare un modello più leggero, ma questo potrebbe ridurre la qualità della pianificazione.

3. **Background LLM**: Può essere più leggero perché non richiede risposte immediate, ma deve comunque essere in grado di eseguire task complessi.

4. **Gemini Support**: Se `llm_provider = "gemini"`, tutti gli LLM usano Gemini invece di Ollama/llama.cpp.

