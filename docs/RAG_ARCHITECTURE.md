# Architettura RAG (Retrieval-Augmented Generation)

## Panoramica

Il sistema Knowledge Navigator utilizza un'architettura RAG per recuperare informazioni rilevanti da file caricati, memoria a medio termine e memoria a lungo termine prima di generare risposte con l'LLM.

## Componenti del Sistema RAG

### 1. **Embedding Service**

**Modello utilizzato**: `all-MiniLM-L6-v2` (SentenceTransformer da HuggingFace)

**Caratteristiche**:
- Modello locale leggero (80MB)
- 384 dimensioni per embedding
- Supporta italiano e inglese
- Caricamento lazy (caricato solo quando necessario)

**Implementazione**: `backend/app/services/embedding_service.py`

```python
from sentence_transformers import SentenceTransformer

class EmbeddingService:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model: Optional[SentenceTransformer] = None
    
    def generate_embedding(self, text: str) -> List[float]:
        """Genera embedding per un singolo testo"""
        self._ensure_model_loaded()
        embedding = self._model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
```

**Nota importante**: Il sistema NON utilizza Ollama né Gemini per le embeddings. Utilizza un modello SentenceTransformer locale che viene scaricato da HuggingFace al primo utilizzo.

### 2. **Vector Database (ChromaDB)**

**Utilizzo**: ChromaDB viene utilizzato per memorizzare embeddings di:
- File caricati nella sessione (`file_embeddings` collection)
- Memoria a medio termine (`session_memory` collection)
- Memoria a lungo termine (`long_term_memory` collection)

**Isolamento Multi-Tenant**: Ogni tenant ha collezioni separate in ChromaDB.

**Storage**:
- **Locale**: ChromaDB Docker container (porta 8001)
- **Cloud**: ChromaDB Cloud (trychroma.com)

### 3. **Retrieval Process**

Il processo di retrieval avviene in `backend/app/core/memory_manager.py`:

#### File Content Retrieval (`retrieve_file_content`)

1. **Riconoscimento ID File**: Se la query contiene un UUID, il sistema cerca direttamente quel file
2. **Riconoscimento Richieste Generiche**: Se la query contiene parole chiave come "riassunto", "analizza", "il file", recupera tutti i file della sessione
3. **Ricerca Semantica**: Altrimenti, usa la ricerca semantica per trovare file rilevanti

```python
async def retrieve_file_content(
    self,
    session_id: UUID,
    query: str,
    n_results: int = 5,
    db: Optional[AsyncSession] = None,
    tenant_id: Optional[UUID] = None,
) -> List[str]:
    # 1. Check for file ID in query
    # 2. Check for generic file request keywords
    # 3. Generate query embedding
    # 4. Query ChromaDB collection
    # 5. Return relevant documents
```

#### Medium-Term Memory Retrieval (`retrieve_medium_term_memory`)

Recupera informazioni da conversazioni precedenti nella stessa sessione.

#### Long-Term Memory Retrieval (`retrieve_long_term_memory`)

Recupera conoscenza persistente tra sessioni diverse.

### 4. **LLM Integration**

Dopo il retrieval, i contenuti recuperati vengono aggiunti al contesto dell'LLM:

**Per Vertex AI** (`backend/app/core/vertex_ai_client.py`):
- I contenuti vengono aggiunti al `system_instruction`
- Distinzione chiara tra file caricati e file Drive

**Per Ollama** (`backend/app/core/ollama_client.py`):
- I contenuti vengono aggiunti al `enhanced_system` prompt
- Stessa distinzione tra file caricati e Drive

**Per Gemini API REST** (`backend/app/core/gemini_client.py`):
- I contenuti vengono aggiunti al `system_instruction`
- Limitati a 3 items per evitare trigger dei safety filters

## Flusso Completo RAG

```
1. User Query
   ↓
2. Generate Query Embedding (SentenceTransformer)
   ↓
3. Query ChromaDB Collections:
   - file_embeddings (file caricati)
   - session_memory (memoria medio termine)
   - long_term_memory (memoria lungo termine)
   ↓
4. Retrieve Top-K Results (semantic similarity)
   ↓
5. Add Retrieved Content to LLM Context:
   - Vertex AI: system_instruction
   - Ollama: enhanced_system
   - Gemini: system_instruction
   ↓
6. LLM Generates Response with Context
```

## Migrazione da Ollama a Gemini

**Embeddings**: Il sistema NON ha mai utilizzato Ollama per le embeddings. Ha sempre utilizzato SentenceTransformer (`all-MiniLM-L6-v2`).

**LLM per Generazione Risposte**: 
- **Prima**: Ollama (locale) o Gemini API REST
- **Ora**: Vertex AI (Gemini 2.5 Flash), Ollama, o Gemini API REST (configurabile)

**Nota**: Le embeddings sono sempre state generate localmente con SentenceTransformer, indipendentemente dal provider LLM scelto per la generazione.

## Configurazione

### Variabili d'Ambiente

```bash
# Embedding Model (opzionale, default: all-MiniLM-L6-v2)
EMBEDDING_MODEL=all-MiniLM-L6-v2

# HuggingFace Token (opzionale, aiuta a evitare rate limits)
HUGGINGFACE_TOKEN=your_token_here

# ChromaDB
CHROMADB_HOST=localhost:8001  # Locale
# oppure
CHROMADB_HOST=your-chromadb-instance.trychroma.com  # Cloud
```

## Troubleshooting

### File non trovato per ID

Se un file caricato non viene trovato quando si menziona il suo ID:

1. Verifica che il file esista nel database: `GET /api/files/id/{file_id}`
2. Verifica che l'embedding esista in ChromaDB: controlla i log per `file_id` nei metadati
3. Verifica che il file appartenga alla sessione corretta

### Embeddings non generati

Se le embeddings non vengono generate durante l'upload:

1. Verifica che il file contenga testo estraibile
2. Controlla i log per errori durante la generazione dell'embedding
3. Verifica la connessione a ChromaDB

### Rate Limits HuggingFace

Se si verificano errori 429 (rate limit) durante il caricamento del modello:

1. Imposta `HUGGINGFACE_TOKEN` per autenticazione
2. Il sistema implementa retry con backoff esponenziale
3. Considera di precaricare il modello all'avvio

## Riferimenti

- [SentenceTransformers Documentation](https://www.sbert.net/)
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [HuggingFace Model Hub](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)

