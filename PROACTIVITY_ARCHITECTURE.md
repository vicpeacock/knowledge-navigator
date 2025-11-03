# Architettura Proattività - Knowledge Navigator

## Panoramica

Il Knowledge Navigator originale poteva "prendere la parola" quando arrivavano email, eventi del calendario o altri eventi esterni. Questa funzionalità richiede:

1. **Sistema di Eventi**: Monitoraggio continuo di fonti esterne
2. **Motore Decisionale**: Valuta se e quando interrompere l'utente
3. **Notifiche Real-time**: Comunicazione bidirezionale backend-frontend
4. **Priorità e Filtri**: Configurazione utente per cosa ricevere

---

## 1. Architettura Event-Driven

### Backend - Event Monitor Service

```
backend/app/services/
  ├── event_monitor.py        # Monitor principale per eventi esterni
  ├── event_processor.py      # Elabora eventi e decide priorità
  ├── notification_service.py # Gestisce invio notifiche
  └── schedulers/
      ├── email_poller.py     # Polling email (IMAP/Gmail API)
      ├── calendar_watcher.py # Monitor eventi calendario
      ├── whatsapp_monitor.py # Monitor messaggi WhatsApp
      └── system_events.py    # Eventi sistema (reminder, etc.)
```

### Tipi di Eventi

```python
class EventType(str, Enum):
    EMAIL_RECEIVED = "email_received"
    EMAIL_IMPORTANT = "email_important"  # Email da contatti importanti
    CALENDAR_EVENT_STARTING = "calendar_starting"  # Meeting tra 15 min
    CALENDAR_REMINDER = "calendar_reminder"
    WHATSAPP_MESSAGE = "whatsapp_message"
    WHATSAPP_URGENT = "whatsapp_urgent"
    SYSTEM_REMINDER = "system_reminder"
    FILE_UPLOADED = "file_uploaded"  # Se upload da altri dispositivi
    KNOWLEDGE_UPDATE = "knowledge_update"  # Nuove informazioni apprese
```

### Priorità Eventi

```python
class EventPriority(str, Enum):
    LOW = "low"           # Info, non interrompe
    MEDIUM = "medium"     # Notifica discreta
    HIGH = "high"         # Notifica visibile, può interrompere
    URGENT = "urgent"    # Interrompe sempre, richiede attenzione
```

---

## 2. Sistema Real-time (WebSocket)

### Backend - WebSocket Endpoint

```python
# backend/app/api/notifications.py
from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
    
    async def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
    
    async def send_notification(self, session_id: str, notification: dict):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(notification)
```

### Frontend - WebSocket Client

```typescript
// frontend/hooks/useWebSocket.ts
// Hook React per gestire connessione WebSocket
// Riceve notifiche e le mostra come messaggi proattivi
```

---

## 3. Motore Decisionale

### Logica di Priorità

```python
class EventProcessor:
    def should_interrupt(self, event: Event, user_context: dict) -> bool:
        """
        Decide se interrompere l'utente basandosi su:
        - Priorità evento
        - Stato utente (in call? in focus?)
        - Preferenze utente
        - Pattern storici (es: sempre interrompe per email da X)
        """
        
        priority = event.priority
        
        # Urgent sempre interrompe
        if priority == EventPriority.URGENT:
            return True
        
        # High interrompe se utente non occupato
        if priority == EventPriority.HIGH:
            return not user_context.get('busy', False)
        
        # Medium solo notifica
        if priority == EventPriority.MEDIUM:
            return False  # Notifica discreta
        
        # LOW solo log, no notifica
        return False
    
    def generate_proactive_message(self, event: Event) -> str:
        """
        Genera messaggio proattivo usando LLM
        Es: "Ho ricevuto un'email da Mario Rossi con oggetto 'Progetto X'. Vuoi che te la riassuma?"
        """
        prompt = f"Genera un messaggio proattivo per questo evento: {event.summary}"
        # Usa Ollama per generare messaggio naturale
        return llm_response
```

---

## 4. Flusso Completo

```
1. Event Monitor rileva evento esterno (es: email)
   ↓
2. Event Processor valuta priorità e rilevanza
   ↓
3. Se rilevante → genera messaggio proattivo con LLM
   ↓
4. Notification Service invia via WebSocket al frontend
   ↓
5. Frontend mostra notifica/messaggio proattivo
   ↓
6. Utente può rispondere o ignorare
```

---

## 5. Configurazione Utente

### Preferenze Notifiche

```typescript
interface NotificationPreferences {
  email: {
    enabled: boolean
    only_from_contacts: boolean
    priority_keywords: string[]
    quiet_hours: { start: string, end: string }
  }
  calendar: {
    enabled: boolean
    reminder_minutes: number[]  // [15, 5] → reminder a 15 e 5 min prima
    only_my_events: boolean
  }
  whatsapp: {
    enabled: boolean
    only_from_contacts: boolean
    urgent_keywords: string[]
  }
  proactive_mode: 'always' | 'smart' | 'never'
  interruption_level: 'high' | 'medium' | 'low'
}
```

---

## 6. Implementazione Step-by-Step

### Step 1: WebSocket Infrastructure
- [ ] Backend WebSocket endpoint
- [ ] Frontend WebSocket hook
- [ ] Gestione connessioni multiple sessioni

### Step 2: Event Monitor Base
- [ ] Polling email (Gmail/IMAP)
- [ ] Polling calendario
- [ ] Event queue system

### Step 3: Event Processor
- [ ] Sistema priorità
- [ ] Filtri configurabili
- [ ] Generazione messaggi proattivi

### Step 4: UI Notifiche
- [ ] Componente notifica proattiva
- [ ] Modal/Toast per messaggi
- [ ] Badge contatore eventi

### Step 5: Integrazione Completa
- [ ] Email → notifica automatica
- [ ] Calendario → reminder proattivi
- [ ] WhatsApp → messaggi urgenti

---

## 7. Esempi Messaggi Proattivi

### Email
- "Ho ricevuto un'email da Maria Rossi con oggetto 'Meeting urgente'. Vuoi che te la legga?"
- "C'è un'email importante non letta da 2 ore. Vuoi che te la riassuma?"

### Calendario
- "Hai un meeting tra 15 minuti: 'Review Progetto X' con il team. Vuoi un riassunto del progetto?"
- "Il tuo evento 'Pranzo con cliente' sta per iniziare tra 10 minuti. Vuoi informazioni sul cliente?"

### WhatsApp
- "Hai ricevuto un messaggio da Mario: 'Urgente: possiamo parlare?'. Vuoi rispondere?"
- "Nuovo messaggio in gruppo 'Team Lavoro'. Vuoi che lo riassuma?"

### Sistema
- "Ho notato che lavori spesso su documenti PDF al mattino. Vuoi che prepari un riassunto dei tuoi file più recenti?"
- "Ho appreso nuove informazioni su 'Machine Learning' dalle nostre conversazioni. Vuoi che aggiorni la tua knowledge base?"

---

## 8. Considerazioni Tecniche

### Polling vs Webhook
- **Email**: Gmail API push notifications (webhook), IMAP polling
- **Calendario**: Google Calendar push, Apple CalDAV polling
- **WhatsApp**: Polling (API limitate)

### Performance
- Rate limiting su polling
- Batch processing eventi
- Caching stato precedente per evitare duplicati

### Privacy
- Nessun contenuto sensibile nei log
- Crittografia dati in transito
- Configurazione opt-in per ogni tipo evento

