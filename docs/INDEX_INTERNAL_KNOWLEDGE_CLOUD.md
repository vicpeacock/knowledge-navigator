# Indicizzazione Documenti Auto-Coscienza su Cloud Run

## 🚀 Metodo: Script Automatico

Ho creato uno script che chiama l'endpoint API per indicizzare i documenti su Cloud Run.

### Esecuzione

```bash
cd backend/scripts
python3 index_internal_knowledge_cloud.py
```

Lo script ti chiederà:
1. Email admin
2. Password admin

Poi eseguirà automaticamente:
1. Login come admin
2. Chiamata all'endpoint `/api/init/index-internal-knowledge`
3. Indicizzazione di tutti i file `INTERNAL_*.md`

### Output Atteso

```
✅ Autenticazione riuscita
📚 Indicizzazione documenti...
✅ Indicizzazione completata!

📊 Risultati:
   - Totale chunks indicizzati: XXX
   - Documenti processati: 7

📄 Documenti indicizzati:
   ✅ INTERNAL_KNOWLEDGE_NAVIGATOR_ARCHITECTURE.md: XX chunks
   ✅ INTERNAL_MEMORY_SYSTEM.md: XX chunks
   ...
```

## 🌐 Metodo Alternativo: Chiamata Manuale API

Puoi anche chiamare l'endpoint manualmente:

### 1. Login come Admin

```bash
curl -X POST https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "your-admin@email.com", "password": "your-password"}'
```

Salva il `access_token` dalla risposta.

### 2. Chiama Endpoint Indicizzazione

```bash
curl -X POST https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app/api/init/index-internal-knowledge \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json"
```

## ✅ Verifica Post-Indicizzazione

Dopo l'indicizzazione, verifica con:

1. **Test Chat**: Fai una domanda meta come "Come funziona il sistema di memoria?"
2. **Controlla Log**: Cerca messaggi di recupero `internal_knowledge` nei log
3. **Risposta**: La risposta dovrebbe includere informazioni dalla documentazione interna

## 📝 Note

- L'endpoint è protetto e richiede autenticazione admin
- L'indicizzazione può richiedere alcuni minuti (dipende dal numero di documenti)
- I documenti vengono re-indicizzati (vecchi chunks vengono eliminati prima)
- La collection `internal_knowledge` è condivisa tra tutti i tenant

