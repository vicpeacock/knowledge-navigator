# Guida Rollback Cloud Run

## 🔄 Come Fare Rollback al Deploy Precedente

### Metodo 1: Script Automatico (Consigliato)

```bash
./cloud-run/rollback.sh
```

Lo script:
1. Lista tutte le revisioni disponibili
2. Mostra la revisione corrente e quella precedente
3. Chiede conferma
4. Esegue il rollback automaticamente

### Metodo 2: Comando Manuale

```bash
# 1. Lista revisioni
gcloud run revisions list \
    --service=knowledge-navigator-backend \
    --region=us-central1 \
    --project=526374196058 \
    --limit=10

# 2. Identifica la revisione precedente (la seconda nell'elenco)
PREVIOUS_REVISION="knowledge-navigator-backend-XXXXX"

# 3. Esegui rollback
gcloud run services update-traffic knowledge-navigator-backend \
    --to-revisions="${PREVIOUS_REVISION}=100" \
    --region=us-central1 \
    --project=526374196058
```

### Metodo 3: Via Console Web

1. Vai su: https://console.cloud.google.com/run
2. Seleziona il progetto: `526374196058`
3. Clicca sul servizio: `knowledge-navigator-backend`
4. Vai su tab "REVISIONS"
5. Trova la revisione precedente
6. Clicca sui "..." → "Manage Traffic"
7. Imposta 100% traffic sulla revisione precedente

## 📋 Verifica Stato Deploy

```bash
# Verifica stato servizio
gcloud run services describe knowledge-navigator-backend \
    --region=us-central1 \
    --project=526374196058 \
    --format="table(status.url,status.latestReadyRevisionName)"

# Verifica logs (per debug)
gcloud run services logs read knowledge-navigator-backend \
    --region=us-central1 \
    --project=526374196058 \
    --limit=50
```

## ⚠️ Note Importanti

- Il rollback è **immediato** e **reversibile**
- Puoi tornare alla nuova revisione in qualsiasi momento
- Le revisioni precedenti non vengono eliminate automaticamente
- Il traffico viene rediretto alla revisione specificata

## 🚨 In Caso di Problemi Critici

Se il servizio non risponde:

```bash
# 1. Verifica se il servizio è down
curl https://knowledge-navigator-backend-526374196058.us-central1.run.app/health

# 2. Se down, rollback immediato
./cloud-run/rollback.sh

# 3. Verifica logs per capire il problema
gcloud run services logs read knowledge-navigator-backend \
    --region=us-central1 \
    --limit=100
```

