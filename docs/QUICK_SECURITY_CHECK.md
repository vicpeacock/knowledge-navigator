# Quick Security Check - Prima di Rendere Pubblico

## ⚠️ CRITICO: Ruotare Segreti Esposti

I seguenti tipi di segreti DEVONO essere ruotati se esposti nella cronologia Git:

1. **Google Gemini API Keys**:
  - Tutte le chiavi API Google esposte devono essere ruotate
  - Formato: AIzaSy... (39 caratteri)

2. **Google OAuth**: Client ID e Secret

3. **Security Keys**: SECRET_KEY, ENCRYPTION_KEY, JWT_SECRET_KEY

4. **Database Password**: Supabase PostgreSQL

**Azioni**:
- Ruota tutte le chiavi su Google Cloud Console
- Cambia password database su Supabase
- Aggiorna Cloud Run Secret Manager

## ✅ File Già Protetti

- `.gitignore` aggiornato
- File con segreti non tracciati da git
- Script di verifica creato: `scripts/verify-secrets-before-public.sh`

## 🚀 Dopo Rotazione Segreti

```bash
# Verifica finale
./scripts/verify-secrets-before-public.sh

# Se tutto OK, rendi pubblico su GitHub
```

**NON rendere pubblico finché i segreti non sono ruotati!**

