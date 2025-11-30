# Implementazione RAG - Knowledge Navigator

## Panoramica

Knowledge Navigator usa Retrieval-Augmented Generation per recuperare informazioni rilevanti prima di generare risposte con LLM.

---

## Componenti RAG

### 1. Embedding Service
- **Modello**: `all-MiniLM-L6-v2` (SentenceTransformer)
- **Dimensioni**: 384 dimensioni
- **Lingue**: Italiano e inglese
- **Storage**: Locale, caricamento lazy

### 2. Vector Database (ChromaDB)
- **Collections**: file_embeddings, session_memory, long_term_memory
- **Isolamento**: Multi-tenant con collezioni separate
- **Storage**: Locale (Docker) o Cloud (ChromaDB Cloud)

### 3. Retrieval Process
1. Generate query embedding
2. Query ChromaDB collections
3. Retrieve top-K results (semantic similarity)
4. Add to LLM context

---

## Flusso Completo

```
User Query
    ↓
Generate Query Embedding
    ↓
Query ChromaDB Collections
    ↓
Retrieve Top-K Results
    ↓
Add to LLM Context
    ↓
LLM Generates Response
```

---

## Integrazione LLM

### Vertex AI
- Contenuti aggiunti a `system_instruction`
- Distinzione file caricati vs Drive

### Ollama
- Contenuti aggiunti a `enhanced_system`
- Stessa distinzione file caricati vs Drive

### Gemini API REST
- Contenuti aggiunti a `system_instruction`
- Limitati a 3 items per evitare safety filters

---

## Troubleshooting

- **File non trovato**: Verifica embedding in ChromaDB
- **Embeddings non generati**: Controlla estrazione testo file
- **Rate limits HuggingFace**: Usa HUGGINGFACE_TOKEN

---

## Riferimenti

- `backend/app/core/memory_manager.py` - Retrieval implementation
- `backend/app/services/embedding_service.py` - Embedding generation
- `docs/RAG_ARCHITECTURE.md` - Documentazione completa
