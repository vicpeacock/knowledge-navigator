# Setup Supabase Database per Cloud Run

## 📋 Informazioni Progetto

- **Project URL**: https://[PROJECT_ID].supabase.co
- **Project Reference**: `[PROJECT_ID]`

## 🔑 Connection String Database

Per ottenere la connection string del database PostgreSQL:

1. **Vai su Supabase Dashboard**
   - Link: https://app.supabase.com/project/[PROJECT_ID]

2. **Vai su Settings → Database**
   - Link diretto: https://app.supabase.com/project/[PROJECT_ID]/settings/database

3. **Trova "Connection string"**
   - Scrolla fino a "Connection string"
   - Seleziona tab **"URI"**
   - Copia la connection string

4. **Formato atteso**:
   ```
   postgresql://postgres:[PASSWORD]@db.[PROJECT_ID].supabase.co:5432/postgres
   ```

5. **Modifica per asyncpg**:
   Sostituisci `postgresql://` con `postgresql+asyncpg://`
   ```
   postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT_ID].supabase.co:5432/postgres
   ```

## 🔐 Password Database

La password del database è quella che hai impostato quando hai creato il progetto Supabase.

Se non la ricordi:
1. Vai su Settings → Database
2. Clicca "Reset database password"
3. Genera una nuova password (salvala!)

## ✅ Checklist

- [ ] Connection string ottenuta da Supabase Dashboard
- [ ] Password database disponibile
- [ ] Connection string modificata per asyncpg (`postgresql+asyncpg://`)
- [ ] Test connection (opzionale)

## 🧪 Test Connection (Opzionale)

```bash
# Installa psql se non ce l'hai
# Mac: brew install postgresql

# Test connection
psql "postgresql://postgres:PASSWORD@db.[PROJECT_ID].supabase.co:5432/postgres"
```

---

**Nota**: L'API Key fornita è per l'API REST di Supabase, non per la connection string del database PostgreSQL.

