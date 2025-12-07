# Troubleshooting: Backend Non Risponde Dopo RLS

## 🔍 Diagnosi Problema

Se il backend non risponde dopo aver abilitato RLS, il problema è probabilmente che le policies RLS stanno bloccando le query del backend.

## 🚨 Soluzione Temporanea: Disabilita RLS

Se il backend è completamente bloccato, disabilita temporaneamente RLS:

1. **Vai al SQL Editor di Supabase**:
   - https://app.supabase.com/project/zdyuqekimdpsmnelzvri/sql/new

2. **Esegui lo script di emergency**:
   - Copia e incolla il contenuto di `scripts/disable-rls-emergency.sql`
   - Esegui lo script

3. **Verifica che il backend riparta**:
   ```bash
   curl https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app/health
   ```

## 🔧 Diagnosi del Problema

### Verifica 1: Quale User Usa il Backend?

Controlla la connection string usata dal backend:

```sql
-- Nel SQL Editor di Supabase, esegui:
SELECT current_user;
```

Se non è `postgres`, questo è il problema! Le policies RLS permettono accesso solo a `current_user = 'postgres'`.

### Verifica 2: Connection Pooling

Se usi connection pooling (porta 6543), il user potrebbe essere diverso:

- **Connection string con pooling**: `postgres.xxxxx@host:6543` (user diverso!)
- **Connection string diretta**: `postgres@host:5432` (user `postgres`)

### Verifica 3: Policies RLS

Controlla se le policies esistono e sono corrette:

```sql
-- Verifica policies esistenti
SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual
FROM pg_policies
WHERE schemaname = 'public'
ORDER BY tablename, policyname;
```

## ✅ Soluzione Permanente

### Opzione 1: Aggiorna Policies per User Corretto

Se il backend usa un user diverso da `postgres`, aggiorna le policies:

```sql
-- Sostituisci 'your_db_user' con il user reale del backend
ALTER POLICY "tenants_modify_backend" ON public.tenants
  USING (current_user IN ('postgres', 'your_db_user'));

-- Fai lo stesso per tutte le altre policies...
```

### Opzione 2: Aggiorna Connection String

Se possibile, assicurati che il backend si connetta come user `postgres`:

1. Verifica la connection string in Cloud Run env vars
2. Assicurati che usi `postgres` come user (non connection pooling user)

### Opzione 3: Policy Permissive Temporanea

Crea una policy permissiva temporanea per debug:

```sql
-- TEMPORANEA - Solo per debug!
DROP POLICY IF EXISTS "tenants_debug" ON public.tenants;
CREATE POLICY "tenants_debug" ON public.tenants
  FOR ALL
  USING (true);  -- Permette tutto (TEMPORANEA!)
```

**⚠️ RIMUOVI questa policy dopo aver trovato il problema!**

## 📊 Verifica Post-Fix

Dopo aver risolto il problema:

1. **Test Health Check**:
   ```bash
   curl https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app/health
   ```

2. **Test Query Database**:
   ```bash
   curl https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app/api/sessions
   ```

3. **Verifica Log**:
   ```bash
   gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=knowledge-navigator-backend" --limit 10 --project knowledge-navigator-477022
   ```

## 🔗 Link Utili

- **Supabase SQL Editor**: https://app.supabase.com/project/zdyuqekimdpsmnelzvri/sql/new
- **Cloud Run Logs**: https://console.cloud.google.com/run/detail/us-central1/knowledge-navigator-backend/logs?project=knowledge-navigator-477022
