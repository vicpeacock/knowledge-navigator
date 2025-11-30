# Setup Database Supabase - Metodo Veloce

## 🎯 Metodo Più Semplice

Se non trovi la connection string nell'interfaccia, usa questo metodo:

### Step 1: Ottieni o Resetta la Password

1. **Vai al Dashboard Supabase**
   - Link: https://app.supabase.com/project/[PROJECT_ID]

2. **Vai su Settings** (icona ingranaggio in basso a sinistra o in alto a destra)

3. **Clicca su "Database"** nel menu

4. **Cerca "Database password"** o **"Reset database password"**

5. **Se non ricordi la password**:
   - Clicca "Reset database password"
   - Genera una nuova password
   - **⚠️ IMPORTANTE: Salvala subito!** (non potrai più vederla)

### Step 2: Usa lo Script Automatico

Una volta che hai la password, esegui:

```bash
./scripts/build-supabase-connection.sh
```

Lo script ti chiederà la password e aggiornerà automaticamente `.env.cloud-run`.

### Step 3: Verifica

```bash
# Verifica che DATABASE_URL sia corretta
grep DATABASE_URL .env.cloud-run
```

## 🔍 Dove Trovare la Password (Alternative)

### Opzione A: Settings → Database
- Dashboard → Settings → Database
- Cerca "Database password" o "Connection info"

### Opzione B: Project Settings → Database  
- Dashboard → Project Settings (icona ingranaggio) → Database
- Cerca "Database password"

### Opzione C: API Settings
- Dashboard → Settings → API
- Potrebbe essere mostrata lì come "Database URL"

### Opzione D: Email di Benvenuto
- Controlla l'email di benvenuto di Supabase
- Potrebbe contenere la password iniziale

## 📝 Connection String Manuale

Se preferisci costruirla manualmente:

**Formato**:
```
postgresql+asyncpg://postgres:LA_TUA_PASSWORD@db.[PROJECT_ID].supabase.co:5432/postgres
```

**Componenti**:
- `postgresql+asyncpg://` - Protocollo (aggiunto `+asyncpg` per il nostro backend)
- `postgres` - Username
- `LA_TUA_PASSWORD` - Password del database
- `db.[PROJECT_ID].supabase.co` - Host
- `5432` - Port
- `postgres` - Database name

**Aggiorna `.env.cloud-run`**:
```bash
DATABASE_URL=postgresql+asyncpg://postgres:LA_TUA_PASSWORD@db.[PROJECT_ID].supabase.co:5432/postgres
POSTGRES_PASSWORD=LA_TUA_PASSWORD
POSTGRES_HOST=db.[PROJECT_ID].supabase.co
```

## ✅ Checklist

- [ ] Password database ottenuta o resettata
- [ ] Script eseguito: `./scripts/build-supabase-connection.sh`
- [ ] File `.env.cloud-run` aggiornato
- [ ] Connection string verificata

---

**Nota**: Se non trovi la password da nessuna parte, il modo più semplice è resettarla. Supabase ti permetterà di generare una nuova password che potrai salvare.

