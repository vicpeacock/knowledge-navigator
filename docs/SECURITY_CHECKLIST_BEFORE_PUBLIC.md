# Security Checklist - Prima di Rendere Pubblico il Repository

**Data**: 2025-11-29  
**Status**: ⚠️ IN VERIFICA

---

## ✅ Verifiche Completate

### 1. File .gitignore
- [x] `.env*` esclusi
- [x] `credentials/` esclusi
- [x] `*.key`, `*.pem` esclusi
- [x] `secrets*` esclusi
- [x] `backups/` esclusi
- [x] File sensibili documentati esclusi (`SECURITY_NOTICE.md`, `DEPLOYMENT_SUMMARY.md`, etc.)

### 2. File con Segreti Rimossi/Censurati
- [x] `backend/scripts/test_gemini_block_none.py` - Rimossa API key hardcoded
- [x] `docs/USER_MANAGEMENT_PLAN.md` - JWT tokens di esempio marcati come esempi
- [x] File con segreti aggiunti a `.gitignore` (non tracciati)

### 3. File Non Tracciati da Git (OK)
- [x] `SECURITY_NOTICE.md` - Contiene segreti ma è in `.gitignore`
- [x] `cloud-run/DEPLOYMENT_SUMMARY.md` - Contiene segreti ma non è tracciato
- [x] `cloud-run/SERVICES_EXPLANATION.md` - Contiene segreti ma non è tracciato
- [x] `backend/scripts/test_new_api_key.md` - Contiene segreti ma non è tracciato
- [x] `backend/scripts/check_gemini_api_key_project.md` - Contiene segreti ma non è tracciato

---

## ⚠️ Azioni Richieste Prima di Rendere Pubblico

### 1. Ruotare Segreti Esposti nella Cronologia Git

I seguenti segreti sono stati esposti nella cronologia Git e **DEVONO essere ruotati**:

#### API Keys
- [x] API Keys in documentation files are example keys (should be rotated if used in production)

#### OAuth Credentials
- [ ] `526374196058-0vnk33472si9t07t6pttg8s7r4jmcuel.apps.googleusercontent.com` - Google OAuth Client ID
- [ ] `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` - Google OAuth Client Secret

#### Security Keys
- [ ] `502503eef7db58eae0565044f5bb2d78700b477f3b5451edcfdaedaa339c401b` - SECRET_KEY
- [ ] `b69c683bace3072335d74d99d86bfd11` - ENCRYPTION_KEY
- [ ] `c0ef367d535d0abd18c794c9dda67c8c56a229ffddd9b965b8980a81cecaacd7` - JWT_SECRET_KEY

#### Database Password
- [ ] `PllVcn_66.superbase` - Supabase PostgreSQL Password

#### Altri Segreti
- [ ] `m243cpsnmiw1qre7gn1z70a749n3u6ghtiyhi9vltr2g84at2b` - MCP Gateway Auth Token
- [ ] `ck-3DKWB3X6yC45ePgrFLEnzQWsbF8qwBwPonJQeaNCSJbp` - ChromaDB Cloud API Key

**Come Ruotare**:
1. Vai su [Google Cloud Console](https://console.cloud.google.com/apis/credentials) per API keys
2. Vai su [Google AI Studio](https://aistudio.google.com/app/apikey) per Gemini API keys
3. Vai su [Supabase Dashboard](https://app.supabase.com) per database password
4. Rigenera tutte le chiavi
5. Aggiorna in Cloud Run Secret Manager
6. Aggiorna in tutti gli ambienti

### 2. Pulire Cronologia Git (Opzionale ma Consigliato)

Se vuoi rimuovere completamente i segreti dalla cronologia Git:

```bash
# Opzione 1: Usa git filter-branch (più sicuro)
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch SECURITY_NOTICE.md" \
  --prune-empty --tag-name-filter cat -- --all

# Opzione 2: Usa BFG Repo-Cleaner (più veloce)
# Scarica da: https://rtyley.github.io/bfg-repo-cleaner/
bfg --replace-text passwords.txt

# Dopo la pulizia, force push (ATTENZIONE: solo se repository non condiviso!)
git push origin --force --all
```

**⚠️ ATTENZIONE**: 
- Questo richiede un force push
- Se altri hanno già fatto pull, devono re-clonare il repository
- Considera di creare un nuovo repository invece di pulire la cronologia

### 3. Verifica Finale

Esegui lo script di verifica:

```bash
./scripts/verify-secrets-before-public.sh
```

Lo script deve restituire:
- ✅ Nessun errore
- ⚠️ Avvisi minimi (solo file di esempio/documentazione)

---

## 📋 Checklist Finale Prima di Rendere Pubblico

- [ ] Tutti i segreti sono stati ruotati
- [ ] Script di verifica passa senza errori
- [ ] Nessun file con segreti è tracciato da git
- [ ] `.gitignore` è completo e corretto
- [ ] Tutti i file sensibili sono esclusi
- [ ] Cronologia Git pulita (opzionale)
- [ ] Cloud Run Secret Manager aggiornato
- [ ] Tutti gli ambienti aggiornati con nuovi segreti

---

## 🚀 Dopo Aver Reso Pubblico

1. **Monitora GitGuardian**: Verifica che non ci siano nuovi alert
2. **Monitora Logs**: Controlla se ci sono tentativi di accesso con vecchie chiavi
3. **Documenta**: Aggiorna `docs/SECURITY_INCIDENT_API_KEYS.md` con le azioni completate

---

## 📚 Riferimenti

- [GitGuardian Dashboard](https://dashboard.gitguardian.com/)
- [Google Cloud Console - API Credentials](https://console.cloud.google.com/apis/credentials)
- [Supabase Dashboard](https://app.supabase.com)
- [OWASP - Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)

---

**IMPORTANTE**: Non rendere pubblico il repository fino a quando tutti i segreti non sono stati ruotati e verificati!

