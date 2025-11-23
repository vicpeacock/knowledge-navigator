# Come Ottenere Connection String da Supabase

## Metodo 1: Dashboard Settings → Database

1. **Vai al Dashboard del tuo progetto**
   - Link: https://app.supabase.com/project/zdyuqekimdpsmnelzvri

2. **Vai su Settings** (icona ingranaggio in basso a sinistra)

3. **Clicca su "Database"** nel menu laterale

4. **Cerca "Connection string"** o **"Connection pooling"**
   - Potrebbe essere sotto "Connection string" o "Connection info"
   - Cerca anche "Connection pooling" che mostra la connection string

5. **Seleziona il tab "URI"** (non "Session mode" o "Transaction mode")

6. **Copia la stringa** che inizia con `postgresql://`

## Metodo 2: Project Settings → Database

1. **Vai al progetto**
   - Link: https://app.supabase.com/project/zdyuqekimdpsmnelzvri

2. **Clicca su "Project Settings"** (icona ingranaggio in alto a destra)

3. **Nel menu laterale, clicca su "Database"**

4. **Cerca "Connection string"** o **"Connection info"**

5. **Seleziona "URI"** e copia la stringa

## Metodo 3: Database → Connection Info

1. **Vai al Database**
   - Link: https://app.supabase.com/project/zdyuqekimdpsmnelzvri/editor

2. **Cerca un pulsante o link "Connection Info"** o **"Settings"**

3. **Clicca e cerca la connection string**

## Metodo 4: Costruisci Manualmente

Se non trovi la connection string, puoi costruirla manualmente:

**Formato**:
```
postgresql://postgres:[PASSWORD]@db.zdyuqekimdpsmnelzvri.supabase.co:5432/postgres
```

**Dove trovare la password**:

1. **Vai su Settings → Database**
2. **Cerca "Database password"** o **"Reset database password"**
3. Se non ricordi la password, puoi resettarla:
   - Clicca "Reset database password"
   - Genera una nuova password
   - **SALVALA!** (non potrai più vederla)

**Informazioni che hai già**:
- Host: `db.zdyuqekimdpsmnelzvri.supabase.co`
- Port: `5432`
- User: `postgres`
- Database: `postgres`

**Ti serve solo**: La password del database

## Metodo 5: API → Connection String

1. **Vai su Settings → API**
2. **Cerca "Database URL"** o **"Connection string"**
3. Potrebbe essere mostrata lì

## Metodo 6: Usa Supabase CLI (Alternativa)

Se hai Supabase CLI installato:

```bash
# Login
supabase login

# Link progetto
supabase link --project-ref zdyuqekimdpsmnelzvri

# Ottieni connection string
supabase db connection-string
```

## Cosa Cercare Esattamente

La connection string che ti serve ha questo formato:
```
postgresql://postgres.xxxxx:[PASSWORD]@aws-0-eu-central-1.pooler.supabase.com:6543/postgres
```

O questo formato (direct connection):
```
postgresql://postgres:[PASSWORD]@db.zdyuqekimdpsmnelzvri.supabase.co:5432/postgres
```

## Se Non Trovi la Password

1. **Vai su Settings → Database**
2. **Cerca "Database password"** o **"Reset database password"**
3. **Clicca "Reset database password"**
4. **Genera nuova password** e salvala subito
5. **Usa questa password** nella connection string

## Formato Finale per .env.cloud-run

Una volta che hai la connection string, modificala così:

**Da**:
```
postgresql://postgres:PASSWORD@db.zdyuqekimdpsmnelzvri.supabase.co:5432/postgres
```

**A** (aggiungi `+asyncpg`):
```
postgresql+asyncpg://postgres:PASSWORD@db.zdyuqekimdpsmnelzvri.supabase.co:5432/postgres
```

E aggiorna `.env.cloud-run`:
```bash
DATABASE_URL=postgresql+asyncpg://postgres:LA_TUA_PASSWORD@db.zdyuqekimdpsmnelzvri.supabase.co:5432/postgres
POSTGRES_PASSWORD=LA_TUA_PASSWORD
```

---

**Nota**: L'interfaccia di Supabase può variare. Se non trovi la connection string, il modo più semplice è resettare la password del database e costruire la connection string manualmente con le informazioni che hai.

