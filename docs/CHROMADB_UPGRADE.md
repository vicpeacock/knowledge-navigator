# Guida Aggiornamento ChromaDB Locale

## 📋 Situazione Attuale

- **Versione attuale**: `chromadb/chroma:0.4.18`
- **Versione client Python**: `chromadb==1.3.5`
- **Problema**: Incompatibilità tra client 1.3.5 e server 0.4.18

## 🎯 Obiettivo

Aggiornare ChromaDB locale a una versione compatibile con il client Python 1.3.5 **senza perdere i dati**.

## 📦 Backup Creato

✅ Backup completato: `backups/chromadb/chromadb-backup-20251123-205816`
- Dimensione: ~11MB
- Contenuto: `chroma.sqlite3` + collezioni

## 🔄 Procedura di Aggiornamento

### Opzione 1: Aggiornamento Automatico (Consigliato)

```bash
./scripts/upgrade-chromadb.sh
```

Questo script:
1. ✅ Crea backup automatico
2. ✅ Ferma il container
3. ✅ Aggiorna `docker-compose.yml` a versione 0.6.0
4. ✅ Riavvia ChromaDB
5. ✅ Verifica che i dati siano accessibili

### Opzione 2: Aggiornamento Manuale

```bash
# 1. Backup (già fatto)
./scripts/backup-chromadb.sh

# 2. Ferma container
docker-compose stop chromadb
docker-compose rm -f chromadb

# 3. Aggiorna docker-compose.yml
# Cambia: chromadb/chroma:0.4.18 -> chromadb/chroma:0.6.0

# 4. Riavvia
docker-compose pull chromadb
docker-compose up -d chromadb

# 5. Verifica
curl http://localhost:8001/api/v1/heartbeat
```

## 🔙 Ripristino Backup (se necessario)

Se l'aggiornamento fallisce o i dati non sono accessibili:

```bash
./scripts/restore-chromadb.sh backups/chromadb/chromadb-backup-20251123-205816
```

Poi ripristina la versione vecchia in `docker-compose.yml`:
```yaml
chromadb:
  image: chromadb/chroma:0.4.18
```

## ⚠️ Note Importanti

1. **Compatibilità**: Il salto da 0.4.18 a 0.6.0 dovrebbe essere compatibile, ma testa sempre
2. **Dati**: I dati sono salvati in `chroma.sqlite3` che dovrebbe essere compatibile
3. **Client Python**: Se 0.6.0 non funziona, potresti dover aggiornare gradualmente:
   - 0.4.18 → 0.5.0 → 0.6.0 → 0.7.0 → ...
4. **Cloud Run**: Non è influenzato (usa ChromaDB Cloud)

## 🧪 Test Post-Aggiornamento

Dopo l'aggiornamento, verifica:

```bash
# 1. Health check
curl http://localhost:8001/api/v1/heartbeat

# 2. Connessione Python
python3 -c "
import chromadb
client = chromadb.HttpClient(host='localhost', port=8001)
collections = client.list_collections()
print(f'Trovate {len(collections)} collezioni')
"

# 3. Riavvia backend
cd backend
./start.sh
curl http://localhost:8000/health
```

## 📊 Versioni ChromaDB

- **0.4.18** (attuale): Vecchia versione, incompatibile con client 1.3.5
- **0.6.0** (target): Versione intermedia, dovrebbe essere compatibile
- **1.x** (futuro): Versione più recente, richiede aggiornamento graduale

---

**Ultimo aggiornamento**: 2025-11-23

