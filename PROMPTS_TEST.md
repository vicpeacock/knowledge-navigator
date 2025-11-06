# Prompt di Test per Miglioramenti Core

## 🎯 Test Auto-Apprendimento

### Test 1: Informazioni Personali
**Conversazione iniziale:**
```
Tu: "Il mio nome è Mario Rossi"
AI: [risponde]

Tu: "Ho 35 anni e lavoro come sviluppatore software"
AI: [risponde]

Tu: "Il mio indirizzo email è mario.rossi@example.com"
AI: [risponde]
```

**Test di recupero (in nuova sessione o dopo qualche messaggio):**
```
Tu: "Qual è il mio nome?"
Tu: "Quanti anni ho?"
Tu: "Qual è la mia email?"
```

**Risultato atteso:** L'AI dovrebbe ricordare tutte le informazioni.

---

### Test 2: Preferenze e Abitudini
**Conversazione iniziale:**
```
Tu: "Preferisco lavorare al mattino, sono più produttivo tra le 8 e le 12"
AI: [risponde]

Tu: "Non mi piace il caffè, preferisco il tè verde"
AI: [risponde]

Tu: "Il mio linguaggio di programmazione preferito è Python"
AI: [risponde]
```

**Test di recupero:**
```
Tu: "Quando sono più produttivo?"
Tu: "Cosa preferisco tra caffè e tè?"
Tu: "Qual è il mio linguaggio preferito?"
```

**Risultato atteso:** L'AI dovrebbe ricordare le preferenze.

---

### Test 3: Eventi e Date Importanti
**Conversazione iniziale:**
```
Tu: "Il mio compleanno è il 15 marzo 1990"
AI: [risponde]

Tu: "Ho un appuntamento importante il 20 dicembre alle 14:00"
AI: [risponde]

Tu: "Il mio anniversario di matrimonio è il 10 giugno"
AI: [risponde]
```

**Test di recupero:**
```
Tu: "Quando è il mio compleanno?"
Tu: "Hai informazioni sul mio appuntamento di dicembre?"
Tu: "Quando è il mio anniversario?"
```

**Risultato atteso:** L'AI dovrebbe ricordare date e eventi.

---

### Test 4: Progetti e Attività
**Conversazione iniziale:**
```
Tu: "Sto lavorando su un progetto chiamato 'Knowledge Navigator'"
AI: [risponde]

Tu: "Il progetto usa Python, FastAPI e Next.js"
AI: [risponde]

Tu: "La deadline del progetto è il 31 gennaio 2025"
AI: [risponde]
```

**Test di recupero:**
```
Tu: "Su quale progetto sto lavorando?"
Tu: "Quali tecnologie uso nel progetto?"
Tu: "Quando è la deadline del progetto?"
```

**Risultato atteso:** L'AI dovrebbe ricordare informazioni sul progetto.

---

### Test 5: Contatti e Relazioni
**Conversazione iniziale:**
```
Tu: "Il mio collega principale si chiama Luca Bianchi, lavora come designer"
AI: [risponde]

Tu: "La mia manager è Anna Verdi, puoi contattarla a anna.verdi@company.com"
AI: [risponde]
```

**Test di recupero:**
```
Tu: "Chi è il mio collega principale?"
Tu: "Come posso contattare la mia manager?"
```

**Risultato atteso:** L'AI dovrebbe ricordare contatti e relazioni.

---

## 🔍 Test Ricerca Semantica Avanzata

### Test 1: Ricerca per Argomento
Dopo aver fatto ricerche web o indicizzato contenuti, prova:

```
Tu: "Cerca informazioni su Python async programming"
Tu: "Cosa sai su machine learning?"
Tu: "Hai informazioni su FastAPI?"
```

**Risultato atteso:** L'AI dovrebbe recuperare contenuti rilevanti dalla memoria long-term.

---

### Test 2: Ricerca Cross-Sessione
1. In una sessione, chiedi: "Cerca informazioni su React hooks"
2. In un'altra sessione, chiedi: "Cosa sai su React?"

**Risultato atteso:** L'AI dovrebbe recuperare informazioni dalla sessione precedente.

---

### Test 3: Ricerca con Keyword Specifiche
```
Tu: "Cerca contenuti che menzionano 'async' e 'await'"
Tu: "Trova informazioni su 'database' e 'PostgreSQL'"
```

**Risultato atteso:** La ricerca ibrida dovrebbe trovare risultati usando sia semantic search che keyword matching.

---

## 🔄 Test Combinati (Auto-Apprendimento + Ricerca)

### Test 1: Apprendimento e Recupero
**Fase 1 - Apprendimento:**
```
Tu: "Il mio stack tecnologico preferito è: Python, FastAPI, PostgreSQL, React"
AI: [risponde]
```

**Fase 2 - Ricerca e utilizzo:**
```
Tu: "Cosa sai su FastAPI?"
Tu: "Quali tecnologie uso nel mio stack?"
```

**Risultato atteso:** L'AI dovrebbe combinare informazioni apprese con contenuti dalla memoria.

---

### Test 2: Apprendimento da Conversazione + Ricerca Web
**Fase 1:**
```
Tu: "Sono interessato a machine learning"
AI: [risponde e potrebbe fare ricerca web]
```

**Fase 2:**
```
Tu: "Cosa ho detto che mi interessa?"
Tu: "Cosa sai su machine learning?"
```

**Risultato atteso:** L'AI dovrebbe ricordare l'interesse e avere informazioni da ricerca web.

---

## 📊 Test di Stress

### Test 1: Molte Informazioni in Sequenza
```
Tu: "Il mio nome è Mario, ho 35 anni, lavoro come sviluppatore, preferisco Python, il mio compleanno è il 15 marzo, la mia email è mario@example.com, sto lavorando su un progetto chiamato 'Knowledge Navigator'"
```

Poi chiedi separatamente ogni informazione per verificare che siano state tutte estratte.

---

### Test 2: Informazioni Contrastanti
```
Tu: "Preferisco lavorare al mattino"
AI: [risponde]

Tu: "In realtà preferisco lavorare la sera"
AI: [risponde]
```

**Risultato atteso:** L'AI dovrebbe aggiornare la preferenza (la più recente dovrebbe avere priorità).

---

## 🎯 Prompt Specifici per Test API

### Test Ricerca Ibrida via API
```bash
# Ricerca semantica pura
curl -X POST http://localhost:8000/api/memory/search/hybrid \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Python async programming",
    "n_results": 5,
    "semantic_weight": 1.0,
    "keyword_weight": 0.0
  }'

# Ricerca keyword pura
curl -X POST http://localhost:8000/api/memory/search/hybrid \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Python async",
    "n_results": 5,
    "semantic_weight": 0.0,
    "keyword_weight": 1.0
  }'

# Ricerca ibrida bilanciata
curl -X POST http://localhost:8000/api/memory/search/hybrid \
  -H "Content-Type: application/json" \
  -d '{
    "query": "machine learning",
    "n_results": 5,
    "semantic_weight": 0.5,
    "keyword_weight": 0.5
  }'
```

### Test Suggerimenti
```bash
curl "http://localhost:8000/api/memory/search/suggest?query=Python&n_suggestions=5"
```

### Test Consolidamento
```bash
# Dopo aver fatto diverse conversazioni, consolida
curl -X POST "http://localhost:8000/api/memory/consolidate/duplicates?similarity_threshold=0.85"
```

---

## ✅ Checklist Test Completo

### Auto-Apprendimento
- [ ] Test informazioni personali (nome, età, email)
- [ ] Test preferenze (orari, cibo, linguaggi)
- [ ] Test eventi e date (compleanno, appuntamenti)
- [ ] Test progetti e attività
- [ ] Test contatti e relazioni
- [ ] Verifica recupero in nuova sessione

### Ricerca Semantica
- [ ] Test ricerca per argomento
- [ ] Test ricerca cross-sessione
- [ ] Test ricerca con keyword
- [ ] Test suggerimenti query
- [ ] Verifica scoring combinato

### Consolidamento
- [ ] Test rimozione duplicati
- [ ] Test sintesi memorie vecchie
- [ ] Verifica che informazioni importanti siano preservate

---

## 📝 Note per il Testing

1. **Attendi qualche secondo** dopo ogni conversazione per permettere all'auto-apprendimento di completarsi (è in background)

2. **Verifica i log** per vedere l'estrazione:
   ```bash
   tail -f backend/logs/backend.log | grep -i "auto-learned"
   ```

3. **Usa sessioni diverse** per testare il cross-session retrieval

4. **Fai ricerche web** prima di testare la ricerca semantica per avere contenuti nella memoria

5. **Testa gradualmente** - inizia con informazioni semplici, poi aumenta la complessità

---

## 🎬 Sequenza di Test Consigliata

1. **Giorno 1 - Auto-Apprendimento Base:**
   - Test 1: Informazioni Personali
   - Test 2: Preferenze
   - Verifica recupero

2. **Giorno 2 - Ricerca Semantica:**
   - Fai alcune ricerche web
   - Test ricerca per argomento
   - Test ricerca cross-sessione

3. **Giorno 3 - Test Combinati:**
   - Test apprendimento + ricerca
   - Test consolidamento
   - Test di stress

