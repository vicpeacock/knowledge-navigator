# Status Chiavi e Credenziali - Verifica per Cloud Run

**Data verifica**: 2025-11-22

## ✅ Chiavi Presenti e Configurate

### 🗄️ Database
- ✅ `DATABASE_URL` - Configurato (ma attualmente punta a localhost)
- ✅ `POSTGRES_HOST` - Configurato (localhost)
- ✅ `POSTGRES_USER` - Configurato
- ✅ `POSTGRES_PASSWORD` - Configurato
- ✅ `POSTGRES_DB` - Configurato

**⚠️ ATTENZIONE**: I valori attuali sono per sviluppo locale. Per Cloud Run serve:
- Database esterno (Supabase/Neon) **O**
- Cloud SQL connection string

### 🤖 LLM Configuration
- ✅ `LLM_PROVIDER=gemini` - **Perfetto per Cloud Run!**
- ✅ `GEMINI_API_KEY` - Presente e configurata
- ✅ `GEMINI_MODEL=gemini-2.5-flash` - Configurato

**✅ Pronto per Cloud Run!**

### 🔐 Security Keys
- ⚠️ `SECRET_KEY` - **VALORE DEFAULT!** Deve essere cambiato
- ⚠️ `ENCRYPTION_KEY` - **VALORE DEFAULT!** Deve essere cambiato
- ⚠️ `JWT_SECRET_KEY` - **VALORE DEFAULT!** Deve essere cambiato

**❌ CRITICO**: Queste chiavi usano ancora i valori di default. **DEVI GENERARE VALORI SICURI** prima del deployment!

### 🔑 Google OAuth
- ✅ `GOOGLE_CLIENT_ID` - Configurato
- ✅ `GOOGLE_CLIENT_SECRET` - Configurato
- ✅ `GOOGLE_OAUTH_CLIENT_ID` - Configurato
- ✅ `GOOGLE_OAUTH_CLIENT_SECRET` - Configurato

**✅ Pronto per Cloud Run!** (Nota: potresti dover aggiornare redirect URIs per Cloud Run)

### 🔍 Google Custom Search
- ✅ `GOOGLE_PSE_API_KEY` - Configurato
- ✅ `GOOGLE_PSE_CX` - Configurato

**✅ Pronto per Cloud Run!**

### 💾 ChromaDB
- ⚠️ `CHROMADB_HOST=localhost` - **Deve essere cambiato per Cloud Run**
- ⚠️ `CHROMADB_PORT=8001` - OK

**⚠️ ATTENZIONE**: Per Cloud Run, ChromaDB deve essere:
- Deployato separatamente su Cloud Run **O**
- Usato come servizio esterno **O**
- Configurato per usare database esterno

### 🔌 MCP Gateway
- ⚠️ `MCP_GATEWAY_URL=http://localhost:8080` - **Deve essere cambiato per Cloud Run**
- ✅ `MCP_GATEWAY_AUTH_TOKEN` - Configurato

**⚠️ ATTENZIONE**: Per Cloud Run, MCP Gateway deve essere deployato separatamente o usare URL esterno.

### 📧 SMTP (Opzionale)
- ⚠️ Non configurato (opzionale, non necessario per demo)

---

## ❌ Cosa Manca o Deve Essere Modificato

### 🔴 CRITICO - Da Fare Prima del Deployment

1. **Security Keys** - Generare valori sicuri:
   ```bash
   # Genera SECRET_KEY (32+ caratteri)
   openssl rand -hex 32
   
   # Genera ENCRYPTION_KEY (esattamente 32 caratteri)
   openssl rand -hex 16
   
   # Genera JWT_SECRET_KEY (32+ caratteri)
   openssl rand -hex 32
   ```

2. **Database URL** - Configurare per Cloud Run:
   - Opzione A: Database esterno (Supabase/Neon)
   - Opzione B: Cloud SQL connection string

3. **ChromaDB** - Configurare per Cloud Run:
   - Deploy ChromaDB separatamente **O**
   - Usare servizio esterno **O**
   - Configurare per database esterno

4. **MCP Gateway URL** - Configurare per Cloud Run:
   - Deploy MCP Gateway separatamente **O**
   - Usare URL esterno se disponibile

5. **Google OAuth Redirect URIs** - Aggiornare:
   - Aggiungere redirect URIs per Cloud Run in Google Cloud Console
   - Formato: `https://your-backend.run.app/api/integrations/calendars/oauth/callback`
   - Formato: `https://your-backend.run.app/api/integrations/emails/oauth/callback`

---

## 📋 Checklist Pre-Deployment

### Prima di Deployare

- [ ] **Security Keys generate** (SECRET_KEY, ENCRYPTION_KEY, JWT_SECRET_KEY)
- [ ] **Database configurato** (esterno o Cloud SQL)
- [ ] **ChromaDB configurato** (deploy separato o esterno)
- [ ] **MCP Gateway configurato** (deploy separato o esterno)
- [ ] **Google OAuth redirect URIs aggiornati** per Cloud Run
- [ ] **File `.env.cloud-run` creato** con tutti i valori corretti

### Durante Deployment

- [ ] **Variabili ambiente configurate** in Cloud Run
- [ ] **Secrets configurati** in Secret Manager (per GEMINI_API_KEY, etc.)
- [ ] **Health checks funzionanti**
- [ ] **Migrations eseguite**

### Dopo Deployment

- [ ] **Test end-to-end** completati
- [ ] **URL pubblici** documentati
- [ ] **Logs verificati**

---

## 🛠️ Script Utili

### Genera Security Keys

```bash
# Genera tutte le security keys necessarie
echo "SECRET_KEY=$(openssl rand -hex 32)"
echo "ENCRYPTION_KEY=$(openssl rand -hex 16)"
echo "JWT_SECRET_KEY=$(openssl rand -hex 32)"
```

### Crea .env.cloud-run

Usa lo script `scripts/prepare-cloud-env.sh` (da creare) per generare automaticamente `.env.cloud-run` dai valori esistenti.

---

## 📝 Prossimi Passi

1. **Genera security keys sicure**
2. **Configura database per Cloud Run** (Supabase/Neon o Cloud SQL)
3. **Configura ChromaDB per Cloud Run**
4. **Configura MCP Gateway per Cloud Run**
5. **Aggiorna Google OAuth redirect URIs**
6. **Crea `.env.cloud-run`** con tutti i valori corretti
7. **Procedi con deployment**

Vedi `cloud-run/SETUP_GUIDE.md` per istruzioni dettagliate.

---

**Ultimo aggiornamento**: 2025-11-22

