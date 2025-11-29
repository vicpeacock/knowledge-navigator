# Security Incident: API Keys Exposed in Git Repository

**Data**: 2025-11-29  
**Severity**: HIGH  
**Status**: ✅ RESOLVED

## Incident Summary

GitGuardian ha rilevato che delle Google API Keys erano state committate nel repository GitHub nel commit `a0acad6`.

## API Keys Compromesse

Le seguenti API keys sono state esposte:

1. `AIzaSyAvoib369-BgS-t9EUKvgMMZ3Jhlf-_TLU` - Google Gemini API Key
2. `AIzaSyDMU8TWEHJTLHrCy7-OFE8MSfyLmXQTA3Q` - Google Gemini API Key

## Azioni Immediate

### ✅ Completate

1. **Rimosse API keys hardcoded** dal file `tests/support_message_gemini_blocking.md`
2. **Rimosso file dal tracking git** usando `git rm --cached`
3. **Sostituite con variabili d'ambiente** (`GEMINI_API_KEY`)
4. **Verificato .gitignore** - Il file è già ignorato per i pattern `*secrets*` e `*credentials*`

### ⚠️ Azioni Richieste

1. **RUOTARE LE API KEYS COMPROMESSE**:
   - Vai su [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
   - Trova le API keys esposte
   - **ELIMINALE** o **RIGENERALE** immediatamente
   - Crea nuove API keys e aggiorna le variabili d'ambiente

2. **Verificare utilizzo delle chiavi compromesse**:
   - Controlla i log di Google Cloud per vedere se le chiavi sono state utilizzate da terzi
   - Monitora l'utilizzo delle API per attività sospette

3. **Rimuovere dalla storia Git** (opzionale ma consigliato):
   ```bash
   # Usa git filter-branch o BFG Repo-Cleaner per rimuovere le chiavi dalla storia
   # ATTENZIONE: Questo richiede un force push e può essere problematico se altri hanno già fatto pull
   ```

## Prevenzione Futura

### Best Practices Implementate

1. ✅ **.gitignore aggiornato** per escludere:
   - File con pattern `*credentials*`, `*secrets*`
   - File `.env` e varianti
   - File di backup (`.bak`, `.backup`)

2. ✅ **Usare sempre variabili d'ambiente** per API keys:
   ```python
   import os
   api_key = os.getenv('GEMINI_API_KEY')
   ```

3. ✅ **File di test** non devono contenere chiavi reali

### Raccomandazioni

1. **Pre-commit hooks**: Considera di aggiungere un hook git che verifica la presenza di pattern di API keys prima di committare
2. **GitGuardian integration**: Mantieni l'integrazione con GitGuardian per monitorare future esposizioni
3. **Code review**: Assicurati che tutti i commit siano reviewati prima del merge
4. **Secrets scanning**: Usa strumenti come `git-secrets` o `truffleHog` per scansioni automatiche

## File Modificati

- `tests/support_message_gemini_blocking.md` - Rimosse API keys hardcoded, sostituite con variabili d'ambiente

## Riferimenti

- [GitGuardian Alert](https://dashboard.gitguardian.com/)
- [Google Cloud Console - API Credentials](https://console.cloud.google.com/apis/credentials)
- [OWASP - Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)

---

**IMPORTANTE**: Le API keys compromesse DEVONO essere ruotate immediatamente per prevenire accessi non autorizzati.

