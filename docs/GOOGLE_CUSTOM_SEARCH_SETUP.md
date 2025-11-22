# Configurazione Google Custom Search per Gemini

## Panoramica

Quando si usa **Gemini** come LLM provider, il sistema utilizza `customsearch_search` invece di `web_search` per le ricerche web. Questo tool utilizza l'API di Google Custom Search (Programmable Search Engine) per fornire risultati di ricerca web.

## Differenza tra Ollama e Gemini

### Ollama
- Usa `web_search` che richiede `OLLAMA_API_KEY`
- Utilizza l'API di ricerca web di Ollama

### Gemini
- Usa `customsearch_search` che richiede `GOOGLE_PSE_API_KEY` e `GOOGLE_PSE_CX`
- Utilizza Google Custom Search API
- È l'alternativa a `web_search` quando si usa Gemini

## Configurazione

### 1. Ottenere le Chiavi API

#### API Key (GOOGLE_PSE_API_KEY)
1. Vai su [Google Cloud Console](https://console.cloud.google.com/)
2. Seleziona o crea un progetto
3. Vai a **APIs & Services** > **Credentials**
4. Clicca su **Create Credentials** > **API Key**
5. Copia la chiave API generata

#### Custom Search Engine ID (GOOGLE_PSE_CX)
1. Vai su [Google Programmable Search Engine](https://programmablesearchengine.google.com/)
2. Clicca su **Create a custom search engine**
3. Configura il motore di ricerca:
   - **Sites to search**: Puoi lasciare vuoto per cercare su tutto il web, oppure specificare siti specifici
   - **Name**: Nome del tuo motore di ricerca
4. Clicca su **Create**
5. Vai su **Setup** > **Basics**
6. Copia il **Search engine ID** (CX)

### 2. Configurare le Variabili d'Ambiente

Aggiungi le seguenti variabili al file `.env`:

```bash
# Google Custom Search Engine (for web search with Gemini)
GOOGLE_PSE_API_KEY=your_api_key_here
GOOGLE_PSE_CX=your_search_engine_id_here
```

**Nota**: Il sistema supporta anche i nomi alternativi `GOOGLE_CSE_API_KEY` e `GOOGLE_CSE_CX` (CSE = Custom Search Engine).

### 3. Verificare la Configurazione

Dopo aver aggiunto le chiavi, riavvia il backend e verifica nei log:

```
✅ Loaded Google Custom Search API key (length: 39)
✅ Loaded Google Custom Search CX: d570cda4c4...
```

## Utilizzo

Il tool `customsearch_search` viene automaticamente utilizzato da Gemini quando l'utente chiede di cercare informazioni sul web. Esempi:

- "Cerca informazioni su Swisspulse"
- "Meteo a Bussigny"
- "Notizie su Python"
- "Informazioni sulla band X"

### Parametri del Tool

- `query` (obbligatorio): La query di ricerca
- `num` (opzionale, default: 10): Numero di risultati da restituire (max 10)

## Limitazioni

- Google Custom Search API ha un limite di **100 query gratuite al giorno**
- Dopo il limite gratuito, è necessario abilitare la fatturazione su Google Cloud
- Il numero massimo di risultati per query è **10**

## Troubleshooting

### Errore: "GOOGLE_PSE_API_KEY not configured"

**Causa**: La chiave API non è configurata o non viene caricata correttamente.

**Soluzione**:
1. Verifica che le chiavi siano nel file `.env`
2. Riavvia il backend per ricaricare le variabili d'ambiente
3. Verifica i log all'avvio per confermare il caricamento

### Errore: "GOOGLE_PSE_CX not configured"

**Causa**: Il Custom Search Engine ID non è configurato.

**Soluzione**:
1. Verifica che `GOOGLE_PSE_CX` sia nel file `.env`
2. Assicurati di aver copiato l'ID corretto dal Programmable Search Engine

### Gemini non usa customsearch_search

**Causa**: Gemini potrebbe non riconoscere quando usare il tool.

**Soluzione**:
1. Verifica nei log che `customsearch_search` sia disponibile: `✅ customsearch_search is available to Gemini`
2. Usa richieste esplicite come "cerca informazioni su X" invece di domande generiche
3. Verifica che il tool non sia disabilitato nelle preferenze utente

## Note Tecniche

- Il tool è definito in `backend/app/core/tool_manager.py` come tool base (built-in)
- L'implementazione è in `_execute_customsearch_search()` nello stesso file
- Il tool viene automaticamente filtrato per Ollama (solo `web_search` e `web_fetch` vengono filtrati)
- I risultati vengono automaticamente indicizzati nella memoria long-term se `auto_index=True`

