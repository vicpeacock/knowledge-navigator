# Sistema Memoria Multi-Livello - Knowledge Navigator

## Panoramica

Knowledge Navigator implementa un sistema di memoria a tre livelli progettato per bilanciare performance, contestualità, e persistenza della conoscenza.

---

## Architettura Memoria

### Short-Term Memory (TTL: 1 ora)

**Scopo**: Contesto immediato della conversazione corrente

**Storage**:
- In-memory cache (dizionario Python)
- PostgreSQL `memory_short` table per persistenza

**Uso**:
- Context immediato durante conversazione
- Informazioni che cambiano frequentemente
- Stato temporaneo della sessione

**Implementazione**:
```python
# backend/app/core/memory_manager.py
self.short_term_memory: Dict[UUID, Dict[str, Any]] = {}
```

### Medium-Term Memory (TTL: 30 giorni)

**Scopo**: Informazioni rilevanti per la sessione corrente ma che possono essere utili nelle sessioni successive

**Storage**:
- PostgreSQL `memory_medium` table
- ChromaDB `session_memory` collection (embeddings per ricerca semantica)

**Uso**:
- Informazioni estratte da conversazioni nella sessione
- Context che può essere rilevante per sessioni future
- Informazioni con scadenza relativamente breve

**Recupero**:
- Ricerca semantica in ChromaDB per rilevanza
- Filtri per session_id e tenant_id

### Long-Term Memory (Persistente)

**Scopo**: Conoscenza persistente cross-sessione dell'utente

**Storage**:
- PostgreSQL `memory_long` table
- ChromaDB `long_term_memory` collection (embeddings per ricerca semantica)

**Uso**:
- Informazioni importanti estratte da tutte le sessioni
- Preferenze utente
- Conoscenza appresa che deve persistere
- Informazioni archiviate quando una sessione viene archiviata

**Recupero**:
- Ricerca semantica in ChromaDB
- Top-K results basati su cosine similarity
- Filtri per user_id e tenant_id

---

## Embedding Service

**Modello**: `all-MiniLM-L6-v2` (SentenceTransformer)

**Caratteristiche**:
- 384 dimensioni per embedding
- Supporta italiano e inglese
- Caricamento lazy (solo quando necessario)
- Modello locale leggero (80MB)

**Implementazione**:
- `backend/app/services/embedding_service.py`
- Genera embeddings per chunk di testo
- Usato per indicizzazione in ChromaDB

**Nota Importante**: Il sistema NON usa Ollama né Gemini per embeddings, solo SentenceTransformer locale.

---

## Memory Operations

### Retrieval (Recupero)

1. **Generate Query Embedding**: Query utente viene convertita in embedding
2. **Query ChromaDB**: Ricerca semantica per similarità (cosine similarity)
3. **Filter Results**: Filtri per tenant_id, user_id, session_id
4. **Top-K Results**: Ritorna K risultati più rilevanti

### Storage (Salvataggio)

1. **Extract Knowledge**: `ConversationLearner` estrae conoscenza da conversazioni
2. **Generate Embeddings**: Chunkizza testo e genera embeddings
3. **Store in ChromaDB**: Salva embeddings con metadati
4. **Store in PostgreSQL**: Salva metadati e riferimenti

### Consolidation (Consolidamento)

1. **Deduplication**: `MemoryConsolidator` trova memorie duplicate (similarity > 0.85)
2. **Merge**: Unisce memorie simili mantenendo quella con importance_score più alto
3. **Contradiction Detection**: `SemanticIntegrityChecker` rileva contraddizioni (confidence > 0.90)

---

## Multi-Tenant Isolation

Ogni tenant ha collezioni ChromaDB separate:
- `file_embeddings_{tenant_id}`
- `session_memory_{tenant_id}`
- `long_term_memory_{tenant_id}`

Query sempre filtrano per tenant_id per garantire isolamento.

---

## Indicizzazione Sessioni Archiviate

Quando una sessione viene archiviata:
1. Tutti i messaggi vengono indicizzati in Long-Term Memory
2. Metadata inclusi: session_id, title, created_at, status, user_id
3. Ricerca futura può recuperare informazioni da sessioni passate

---

## Troubleshooting

### Memory non recuperata
- Verifica che embeddings esistano in ChromaDB
- Controlla filtri tenant_id/user_id
- Verifica similarity threshold

### Performance lente
- Ridurre n_results per retrieval
- Usare chunking più piccolo
- Considerare cache per query frequenti

---

## Riferimenti

- `backend/app/core/memory_manager.py` - Implementazione principale
- `backend/app/services/embedding_service.py` - Service per embeddings
- `backend/app/services/memory_consolidator.py` - Consolidamento memoria
