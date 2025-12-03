# Fix Errori Supabase Security Advisors

## 🔒 Problemi Comuni e Soluzioni

I Security Advisors di Supabase segnalano problemi comuni di sicurezza. Ecco come risolverli:

### 1. **Row Level Security (RLS) Non Abilitato**

**Problema**: Tabelle pubbliche senza RLS possono essere accessibili da chiunque.

**Soluzione**: Abilita RLS su tutte le tabelle.

**Verifica**:
```sql
-- Verifica quali tabelle non hanno RLS
SELECT tablename 
FROM pg_tables 
WHERE schemaname = 'public' 
AND tablename NOT IN (
    SELECT tablename 
    FROM pg_tables t
    JOIN pg_class c ON c.relname = t.tablename
    WHERE c.relrowsecurity = true
);
```

**Fix**:
```sql
-- Abilita RLS su tutte le tabelle
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE files ENABLE ROW LEVEL SECURITY;
ALTER TABLE integrations ENABLE ROW LEVEL SECURITY;

-- Crea policies per isolamento multi-tenant
-- Esempio per users:
CREATE POLICY "Users can only see their own data"
ON users FOR SELECT
USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);

-- Esempio per sessions:
CREATE POLICY "Users can only see sessions from their tenant"
ON sessions FOR SELECT
USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
```

**Nota**: Il nostro backend usa multi-tenant con schema isolation, quindi RLS potrebbe non essere necessario se usi schema separati per tenant.

---

### 2. **Connection Pooling Non Configurato**

**Problema**: Troppe connessioni dirette al database possono esaurire il pool.

**Soluzione**: Usa Connection Pooling di Supabase.

**Configurazione**:
- **Pool Mode**: Transaction (consigliato) o Session
- **Port**: 6543 (pooled) invece di 5432 (direct)

**Modifica DATABASE_URL**:
```
# Prima (direct connection):
postgresql+asyncpg://postgres:PASSWORD@db.zdyuqekimdpsmnelzvri.supabase.co:5432/postgres

# Dopo (connection pooling):
postgresql+asyncpg://postgres:PASSWORD@db.zdyuqekimdpsmnelzvri.supabase.co:6543/postgres?pgbouncer=true
```

**Dove ottenere connection string pooled**:
1. Vai su: https://app.supabase.com/project/zdyuqekimdpsmnelzvri/settings/database
2. Scrolla fino a "Connection pooling"
3. Seleziona "Transaction mode" (per asyncpg)
4. Copia la connection string

**Aggiorna `.env.cloud-run`**:
```bash
# Usa connection pooling
DATABASE_URL=postgresql+asyncpg://postgres.xxxxx:[PASSWORD]@db.zdyuqekimdpsmnelzvri.supabase.co:6543/postgres?pgbouncer=true
```

---

### 3. **SSL/TLS Non Forzato**

**Problema**: Connessioni non criptate possono essere intercettate.

**Soluzione**: Forza SSL nelle connection strings.

**Fix**:
```
# Aggiungi ?sslmode=require alla connection string
postgresql+asyncpg://postgres:PASSWORD@db.zdyuqekimdpsmnelzvri.supabase.co:5432/postgres?sslmode=require
```

**Per connection pooling**:
```
postgresql+asyncpg://postgres.xxxxx:PASSWORD@db.zdyuqekimdpsmnelzvri.supabase.co:6543/postgres?pgbouncer=true&sslmode=require
```

---

### 4. **Password Database Debole**

**Problema**: Password del database troppo semplice.

**Soluzione**: Reset password con password forte.

**Come fare**:
1. Vai su: https://app.supabase.com/project/zdyuqekimdpsmnelzvri/settings/database
2. Clicca "Reset database password"
3. Genera una password forte (minimo 32 caratteri, maiuscole, minuscole, numeri, simboli)
4. **Salva la password** (non potrai più vederla)
5. Aggiorna `DATABASE_URL` in `.env.cloud-run` e Cloud Run env vars

**Genera password sicura**:
```bash
# Usa openssl per generare password sicura
openssl rand -base64 32
```

---

### 5. **IP Allowlist Non Configurato**

**Problema**: Database accessibile da qualsiasi IP.

**Soluzione**: Configura IP allowlist se necessario.

**Nota**: Cloud Run ha IP dinamici, quindi non puoi usare IP allowlist. Invece:
- Usa connection pooling (porta 6543) che è più sicuro
- Assicurati che le credenziali siano sicure
- Usa SSL/TLS obbligatorio

**Per development locale**:
1. Vai su: Settings → Database → Network Restrictions
2. Aggiungi il tuo IP pubblico
3. **Attenzione**: Rimuovi dopo il test, altrimenti blocchi Cloud Run

---

### 6. **API Keys Esposte**

**Problema**: API keys di Supabase esposte nel frontend o in commit.

**Soluzione**: 
- ✅ **Anon Key**: Può essere pubblica (usa RLS per protezione)
- ❌ **Service Role Key**: MAI esporla, solo backend
- ✅ **Database Password**: Solo backend, mai in frontend

**Verifica**:
```bash
# Cerca API keys nei file
grep -r "supabase.*key" frontend/ --exclude-dir=node_modules
grep -r "eyJ" . --exclude-dir={node_modules,.git} | grep -i supabase
```

---

### 7. **Backup Automatici Non Abilitati**

**Problema**: Nessun backup automatico configurato.

**Soluzione**: Abilita Point-in-Time Recovery (PITR).

**Come fare**:
1. Vai su: Settings → Database
2. Abilita "Point-in-Time Recovery" (disponibile su piani Pro+)
3. Configura retention period

**Per piani Free**:
- Fai backup manuali con: `./scripts/export-full-database-from-supabase.sh`

---

## 🚀 Soluzione Rapida: RLS Script Pronto

**Esegui lo script SQL pronto**: `scripts/enable-rls-supabase.sql`

1. Vai a: https://app.supabase.com/project/zdyuqekimdpsmnelzvri/sql/new
2. Copia e incolla il contenuto di `scripts/enable-rls-supabase.sql`
3. Esegui lo script
4. Verifica con la query alla fine dello script

Lo script:
- ✅ Abilita RLS su tutte le 12 tabelle segnalate
- ✅ Crea policies che permettono accesso al backend (ruolo `postgres`)
- ✅ Mantiene backward compatibility (backend continua a funzionare)
- ✅ Aggiunge isolamento multi-tenant a livello database

Vedi `docs/SUPABASE_RLS_SETUP.md` per dettagli completi.

---

## ✅ Checklist Completa

Usa questa checklist per verificare tutti i problemi:

```bash
# 1. Verifica connection pooling
# DATABASE_URL deve usare porta 6543 per pooling
grep "6543" .env.cloud-run || echo "⚠️  Usa connection pooling (porta 6543)"

# 2. Verifica SSL
# DATABASE_URL deve avere ?sslmode=require
grep "sslmode=require" .env.cloud-run || echo "⚠️  Aggiungi ?sslmode=require"

# 3. Verifica password non esposta
# Nessuna password in file committati
git grep "postgres.*:" -- "*.md" "*.sh" || echo "✅ Password non trovata in file text"

# 4. Verifica RLS (se usi RLS invece di schema isolation)
# Esegui query SQL sopra per verificare
```

---

## 🔧 Script di Fix Automatico

Esegui questo script SQL su Supabase per abilitare RLS (se necessario):

```sql
-- Abilita RLS su tutte le tabelle principali
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN 
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public'
        AND tablename IN ('users', 'tenants', 'sessions', 'messages', 'memories', 'files', 'integrations')
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', r.tablename);
        RAISE NOTICE 'RLS enabled on %', r.tablename;
    END LOOP;
END $$;
```

**Nota**: Se usi schema isolation per multi-tenant (un schema per tenant), RLS potrebbe non essere necessario.

---

## 📝 Aggiornamento Connection String

Dopo aver applicato i fix, aggiorna le variabili d'ambiente:

**In Cloud Run**:
```bash
# Aggiorna DATABASE_URL con pooling e SSL
gcloud run services update knowledge-navigator-backend \
  --region us-central1 \
  --project knowledge-navigator-477022 \
  --update-env-vars DATABASE_URL="postgresql+asyncpg://postgres.xxxxx:[PASSWORD]@db.zdyuqekimdpsmnelzvri.supabase.co:6543/postgres?pgbouncer=true&sslmode=require"
```

**In `.env.cloud-run`**:
```bash
# Aggiorna con connection pooling e SSL
DATABASE_URL=postgresql+asyncpg://postgres.xxxxx:[PASSWORD]@db.zdyuqekimdpsmnelzvri.supabase.co:6543/postgres?pgbouncer=true&sslmode=require
```

---

## 🔗 Link Utili

- **Supabase Dashboard**: https://app.supabase.com/project/zdyuqekimdpsmnelzvri
- **Security Advisors**: https://app.supabase.com/project/zdyuqekimdpsmnelzvri/advisors/security
- **Database Settings**: https://app.supabase.com/project/zdyuqekimdpsmnelzvri/settings/database
- **Connection Pooling Docs**: https://supabase.com/docs/guides/database/connecting-to-postgres#connection-pooler

---

**Ultimo aggiornamento**: 2025-12-02

