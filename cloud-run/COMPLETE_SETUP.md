# Completamento Setup Cloud Run

## ✅ Completato

1. **Security Keys generate** ✅
   - `SECRET_KEY`: Generata
   - `ENCRYPTION_KEY`: Generata
   - `JWT_SECRET_KEY`: Generata

2. **Gemini API Key** ✅
   - Configurata in `.env.cloud-run`

3. **Google OAuth** ✅
   - Client ID e Secret configurati

4. **Google Custom Search** ✅
   - API Key e CX configurati

5. **File `.env.cloud-run` creato** ✅
   - Tutti i valori base configurati

## ⚠️ Da Completare

### 1. Database Supabase - Connection String (CRITICO)

**Cosa serve**: La password del database PostgreSQL di Supabase

**Come ottenerla**:

1. Vai su: https://app.supabase.com/project/[PROJECT_ID]/settings/database
2. Scrolla fino a **"Connection string"**
3. Seleziona tab **"URI"**
4. Copia la connection string (formato: `postgresql://postgres:[PASSWORD]@db.[PROJECT_ID].supabase.co:5432/postgres`)

**Modifica per asyncpg**:
- Sostituisci `postgresql://` con `postgresql+asyncpg://`
- Esempio: `postgresql+asyncpg://postgres:YOUR_PASSWORD@db.[PROJECT_ID].supabase.co:5432/postgres`

**Aggiorna `.env.cloud-run`**:
```bash
# Sostituisci [PASSWORD] con la password reale
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@db.[PROJECT_ID].supabase.co:5432/postgres
POSTGRES_PASSWORD=YOUR_PASSWORD
```

### 2. ChromaDB (Opzionale per demo base)

**Opzioni**:
- **Opzione A**: Deploy ChromaDB separatamente su Cloud Run (consigliato per produzione)
- **Opzione B**: Usa servizio esterno (es. ChromaDB Cloud se disponibile)
- **Opzione C**: Per demo base, puoi temporaneamente usare ChromaDB locale (non scalabile)

**Per ora**: Lascia come `localhost` se non vuoi configurare subito. L'app funzionerà ma senza memoria long-term.

### 3. MCP Gateway (Opzionale per demo base)

**Opzioni**:
- **Opzione A**: Deploy MCP Gateway separatamente su Cloud Run
- **Opzione B**: Usa servizio esterno se disponibile
- **Opzione C**: Per demo base, puoi temporaneamente disabilitare MCP tools

**Per ora**: Lascia come `localhost` se non vuoi configurare subito. L'app funzionerà ma senza MCP tools.

### 4. Google OAuth Redirect URIs (Importante)

**Cosa fare**: Aggiorna i redirect URIs in Google Cloud Console per includere gli URL di Cloud Run

**Dopo il deployment**, aggiungi questi redirect URIs:
- `https://your-backend.run.app/api/integrations/calendars/oauth/callback`
- `https://your-backend.run.app/api/integrations/emails/oauth/callback`

**Dove aggiungerli**:
1. Vai su: https://console.cloud.google.com/apis/credentials
2. Seleziona il tuo OAuth 2.0 Client ID
3. Aggiungi gli URI autorizzati

## 📋 Checklist Finale

Prima di procedere con il deployment:

- [ ] **Database Supabase**: Connection string completa con password
- [ ] **ChromaDB**: Configurato (o lasciato per dopo)
- [ ] **MCP Gateway**: Configurato (o lasciato per dopo)
- [ ] **File `.env.cloud-run`**: Verificato e completo

## 🚀 Prossimo Passo

Una volta completato il punto 1 (Database Supabase), puoi procedere con:

```bash
# Verifica configurazione
./scripts/check-env-keys.sh

# Deploy backend
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"
./cloud-run/deploy.sh backend
```

---

**Nota**: Per una demo base funzionante, è sufficiente completare il punto 1 (Database). ChromaDB e MCP Gateway possono essere configurati dopo.

