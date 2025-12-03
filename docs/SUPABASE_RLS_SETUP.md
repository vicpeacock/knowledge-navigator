# Setup Row Level Security (RLS) per Supabase

## 🔒 Problema

Supabase Security Advisors segnala che RLS non è abilitato su 12 tabelle nel database pubblico:
- `alembic_version`
- `tenants`
- `files`
- `messages`
- `memory_medium`
- `notifications`
- `memory_short`
- `memory_long`
- `api_keys`
- `users`
- `integrations`
- `sessions`

## ✅ Soluzione

Esegui lo script SQL `scripts/enable-rls-supabase.sql` nel SQL Editor di Supabase.

### Come Eseguire lo Script

1. **Vai al SQL Editor di Supabase**:
   - Link: https://app.supabase.com/project/zdyuqekimdpsmnelzvri/sql/new

2. **Copia e incolla** il contenuto di `scripts/enable-rls-supabase.sql`

3. **Esegui lo script** (premi "Run" o Cmd/Ctrl+Enter)

4. **Verifica** che tutte le tabelle abbiano RLS abilitato eseguendo la query di verifica alla fine dello script

## 🔧 Cosa Fa lo Script

### 1. Crea Funzioni Helper

Crea due funzioni per estrarre il `tenant_id`:

- **`auth.tenant_id()`**: Estrae tenant_id dal JWT token o header
- **`app.current_tenant_id()`**: Legge da variabile di sessione PostgreSQL

### 2. Abilita RLS

Abilita RLS su tutte le tabelle menzionate.

### 3. Crea Policies

Crea policies per ogni tabella che:
- ✅ Permettono SELECT/INSERT/UPDATE/DELETE solo se `tenant_id` corrisponde
- ✅ Permettono accesso completo a `service_role` (backend)

### 4. Policy Speciale per `alembic_version`

La tabella `alembic_version` (usata da Alembic per le migrations) ha una policy che permette accesso solo a `service_role`, necessario per eseguire migrations.

## ⚠️ Importante: Backend Deve Impostare Tenant ID

**Il backend DEVE impostare il tenant_id prima di ogni query quando RLS è abilitato**.

### ✅ Soluzione Implementata

È stato creato `get_db_with_tenant()` in `backend/app/core/db_tenant.py` che combina `get_tenant_id()` e `get_db()` e imposta automaticamente `app.current_tenant_id` nella sessione PostgreSQL.

**Nota**: Il backend attualmente filtra tutte le query per `tenant_id` a livello applicativo, quindi i dati sono già isolati per tenant. L'abilitazione di RLS è principalmente per soddisfare i Security Advisors di Supabase e aggiungere un livello extra di sicurezza a livello database.

### Opzionale: Usa `get_db_with_tenant()` nei Nuovi Endpoint

Per i nuovi endpoint, puoi usare `get_db_with_tenant()` invece di `get_db()`:

```python
from app.core.db_tenant import get_db_with_tenant

@router.get("/sessions")
async def get_sessions(db: AsyncSession = Depends(get_db_with_tenant)):
    # RLS sarà automaticamente applicato basandosi su tenant_id
    result = await db.execute(select(Session))
    return result.scalars().all()
```

**Importante**: Le policies RLS create permettono accesso completo a `service_role`, quindi il backend continuerà a funzionare anche senza aggiornare tutti gli endpoint immediatamente.

## 🧪 Verifica

Dopo aver eseguito lo script, verifica che:

1. **RLS è abilitato**: Esegui la query di verifica nello script
2. **Policies funzionano**: Testa una query senza impostare tenant_id (dovrebbe fallire)
3. **Security Advisors**: Controlla che gli errori siano risolti

### Query di Test

```sql
-- Dovrebbe restituire "RLS Enabled" per tutte le tabelle
SELECT 
    tablename,
    CASE 
        WHEN rowsecurity THEN '✅ RLS Enabled'
        ELSE '❌ RLS Disabled'
    END as rls_status
FROM pg_tables t
JOIN pg_class c ON c.relname = t.tablename
WHERE schemaname = 'public'
  AND tablename IN (
    'tenants', 'users', 'sessions', 'messages', 'files',
    'memory_short', 'memory_medium', 'memory_long',
    'integrations', 'notifications', 'api_keys', 'alembic_version'
  )
ORDER BY tablename;
```

## 🔄 Backend - Supporto RLS (Opzionale)

Il backend attualmente filtra tutte le query per `tenant_id` a livello applicativo, quindi i dati sono già isolati per tenant. L'abilitazione di RLS aggiunge un livello extra di sicurezza a livello database.

### ✅ Soluzione Pronta

È stato creato `get_db_with_tenant()` che imposta automaticamente `app.current_tenant_id`. Puoi usarlo nei nuovi endpoint:

```python
from app.core.db_tenant import get_db_with_tenant

@router.get("/sessions")
async def get_sessions(db: AsyncSession = Depends(get_db_with_tenant)):
    # RLS applicato automaticamente
    result = await db.execute(select(Session))
    return result.scalars().all()
```

### ⚠️ Importante

Le policies RLS create permettono accesso completo a `service_role` (usato dal backend), quindi:
- ✅ Il backend continuerà a funzionare senza modifiche
- ✅ Le migrations Alembic continueranno a funzionare
- ✅ I dati sono già isolati per tenant a livello applicativo

Non è necessario aggiornare immediatamente tutti gli endpoint esistenti.

## 📝 Note

1. **Connection Pooling**: Se usi connection pooling (porta 6543), ogni nuova connessione dal pool deve impostare il tenant_id.

2. **Service Role**: Il backend usa `service_role` per le migrations e operazioni amministrative. Le policies permettono accesso completo a `service_role`.

3. **Testing**: Dopo aver abilitato RLS, testa che:
   - Le query del backend funzionano ancora
   - Le migrations Alembic funzionano ancora
   - Non ci sono errori di "permission denied"

## 🔗 Link Utili

- **Supabase SQL Editor**: https://app.supabase.com/project/zdyuqekimdpsmnelzvri/sql/new
- **Security Advisors**: https://app.supabase.com/project/zdyuqekimdpsmnelzvri/advisors/security
- **RLS Docs**: https://supabase.com/docs/guides/auth/row-level-security
- **JWT Claims**: https://supabase.com/docs/guides/auth/jwts

## ✅ Checklist

- [ ] Script SQL eseguito nel Supabase SQL Editor
- [ ] Query di verifica mostra "RLS Enabled" per tutte le tabelle
- [ ] Backend aggiornato per impostare `app.current_tenant_id`
- [ ] Testato che le query del backend funzionano ancora
- [ ] Testato che le migrations Alembic funzionano ancora
- [ ] Security Advisors non mostra più errori RLS
