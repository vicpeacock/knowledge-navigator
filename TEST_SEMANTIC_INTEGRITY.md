# Test Controllo Integrità Semantica

## Come Testare

Il sistema di controllo integrità semantica funziona automaticamente quando viene indicizzata nuova conoscenza. Per testarlo:

### Test 1: Contraddizione Data di Nascita

1. Apri una sessione di chat
2. Di qualcosa che contraddice una memoria esistente, ad esempio:
   - Se in memoria c'è "Data di nascita: 12 luglio 1966"
   - Di: "Sono nato il 20 agosto 1966"
3. Il sistema dovrebbe:
   - Indicizzare la nuova conoscenza
   - In background, controllare le contraddizioni
   - Creare una notifica se trova una contraddizione
   - Mostrare la notifica nella prossima risposta

### Test 2: Contraddizione Stato

1. Di: "Sono single"
2. Poi di: "Ho una moglie"
3. Dovrebbe rilevare la contraddizione

### Test 3: Contraddizione Preferenza

1. Di: "Preferisco il caffè"
2. Poi di: "Non mi piace il caffè"
3. Dovrebbe rilevare la contraddizione

## Verifica Notifiche

Dopo aver creato una contraddizione, puoi verificare le notifiche:

```bash
curl http://localhost:8000/api/notifications/
```

O controlla nella risposta della chat - le notifiche high urgency vengono mostrate automaticamente.

## Note

- Il controllo avviene in background (non blocca la risposta)
- Le notifiche high urgency vengono mostrate immediatamente nella risposta
- Il sistema funziona in qualsiasi lingua (non dipende da keywords)

