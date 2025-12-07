# Analisi di Sicurezza: RLS Setup per Supabase

## 🔒 Analisi dei Rischi

### ✅ Protezioni Implementate

1. **Backend Access Garantito**
   - Tutte le policies includono: `OR current_user = 'postgres'`
   - Il backend si connette come user `postgres` dalla connection string
   - ✅ **Garanzia**: Il backend può sempre accedere ai dati

2. **Alembic Migrations**
   - Alembic usa la stessa connection string del backend (`DATABASE_URL`)
   - Si connette come user `postgres`
   - Policy per `alembic_version`: `current_user = 'postgres'`
   - ✅ **Garanzia**: Le migrations continueranno a funzionare

3. **Rollback Facile**
   - RLS può essere disabilitato con: `ALTER TABLE ... DISABLE ROW LEVEL SECURITY`
   - Lo script include sezione ROLLBACK commentata
   - ✅ **Garanzia**: Possibilità di revert immediato se necessario

### ⚠️ Potenziali Problemi (Analizzati)

1. **User Database Diverso da 'postgres'**
   - **Rischio**: Se il user nella connection string non è `postgres`, le policies non funzioneranno
   - **Protezione**: Script `enable-rls-supabase-safe.sql` verifica il user PRIMA di applicare modifiche
   - **Soluzione**: Verifica con `scripts/verify-database-user.sql`

2. **Connection Pooling**
   - **Rischio**: Se usi connection pooling (porta 6543), il user potrebbe essere diverso
   - **Protezione**: Le policies usano `current_user` che riflette il user della connessione reale
   - **Verifica**: Controlla la connection string - se usa `postgres.xxxxx@host:6543`, potrebbe essere un ruolo diverso

3. **Supabase API REST vs Direct Connection**
   - **Rischio**: Se qualcuno accede tramite Supabase API REST senza auth, potrebbe essere bloccato
   - **Protezione**: Policy include `OR auth.role() = 'service_role'` per API REST
   - **Nota**: Il backend usa direct connection, non API REST

## 🧪 Test di Sicurezza

### Prima di Applicare RLS

```sql
-- 1. Verifica user corrente
SELECT current_user;

-- 2. Verifica che sei connesso correttamente
SELECT COUNT(*) FROM public.tenants;

-- 3. Verifica che Alembic può accedere
SELECT * FROM public.alembic_version;
```

### Dopo aver Applicato RLS

```sql
-- 1. Verifica che RLS è abilitato
SELECT tablename, rowsecurity 
FROM pg_tables t
JOIN pg_class c ON c.relname = t.tablename
WHERE schemaname = 'public' AND tablename = 'tenants';

-- 2. Verifica che puoi ancora leggere (come postgres)
SELECT COUNT(*) FROM public.tenants;
SELECT current_user;  -- Dovrebbe essere 'postgres'

-- 3. Testa una query normale
SELECT id, name FROM public.tenants LIMIT 1;
```

### Test Backend

Dopo aver applicato RLS:

1. **Test Migrations**:
   ```bash
   cd backend
   alembic upgrade head
   ```

2. **Test Backend Startup**:
   ```bash
   python -m uvicorn app.main:app --reload
   # Verifica che si connetta senza errori
   ```

3. **Test API Endpoints**:
   ```bash
   curl http://localhost:8000/health
   # Verifica che restituisca dati
   ```

## 🚨 Procedure di Rollback

### Rollback Completo (Disabilita RLS)

```sql
ALTER TABLE public.tenants DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.users DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.sessions DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.files DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_short DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_medium DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.memory_long DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.integrations DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.notifications DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.api_keys DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.alembic_version DISABLE ROW LEVEL SECURITY;
```

### Rollback Parziale (Rimuovi solo una policy problematica)

```sql
-- Esempio: rimuovi policy da users se causa problemi
DROP POLICY IF EXISTS "users_tenant_isolation" ON public.users;

-- Crea policy più permissiva
CREATE POLICY "users_tenant_isolation" ON public.users
  FOR ALL
  USING (true);  -- Permetti tutto (temporaneo, per debug)
```

## ✅ Checklist Pre-Applicazione

Prima di eseguire lo script RLS:

- [ ] Eseguito `scripts/verify-database-user.sql` - user è `postgres`?
- [ ] Connection string verificata - usa user `postgres`?
- [ ] Backup database fatto (opzionale ma consigliato)
- [ ] Backend non è in produzione critica (o hai piano di rollback)
- [ ] Test locale fatto se possibile

## ✅ Checklist Post-Applicazione

Dopo aver eseguito lo script RLS:

- [ ] Query di verifica mostra "RLS Enabled" per tutte le tabelle
- [ ] Test query funziona: `SELECT COUNT(*) FROM public.tenants;`
- [ ] Backend si avvia senza errori
- [ ] API endpoints rispondono correttamente
- [ ] Alembic migrations funzionano (se testate)
- [ ] Security Advisors non mostra più errori RLS

## 📊 Impatto Stimato

- **Rischio Database Corruption**: ⭐⭐⭐⭐⭐ (ZERO - RLS non modifica dati)
- **Rischio Backend Blocco**: ⭐ (MOLTO BASSO - policies permettono postgres)
- **Rischio Migrations Blocco**: ⭐ (MOLTO BASSO - stessa protezione)
- **Reversibilità**: ⭐⭐⭐⭐⭐ (FACILE - disabilita RLS)

## 🎯 Conclusione

Lo script è **sicuro** perché:

1. ✅ Non modifica dati esistenti
2. ✅ Non cambia schema o struttura
3. ✅ Permette accesso completo al user `postgres` (backend)
4. ✅ Facilmente reversibile
5. ✅ Verifica user prima di applicare (versione safe)

**Raccomandazione**: Usa `enable-rls-supabase-safe.sql` che include verifiche preliminari.
