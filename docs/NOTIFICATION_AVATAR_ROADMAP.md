# Notification System with Avatar - Roadmap

## 🎯 Obiettivo

Implementare un sistema di notifiche avanzato con avatar che riconosce la presenza dell'utente e mostra notifiche contestuali.

---

## ✅ Implementazione Attuale (Completata)

### Link Sessione nelle Notifiche

1. **Backend** (`backend/app/api/sessions.py`):
   - Aggiunto `session_id`, `session_link`, e `has_session` al contenuto delle notifiche email
   - Le notifiche ora includono il link alla sessione automatica se creata

2. **Frontend** (`frontend/components/NotificationBell.tsx`):
   - Pulsante "Apri Sessione →" quando la notifica ha una sessione associata
   - Navigazione automatica alla sessione usando Next.js router
   - Chiusura automatica del popup dopo la navigazione
   - Visualizzazione migliorata per email e calendar notifications

---

## 🚀 Prossimi Passi - Sistema Avatar

### Fase 1: Rilevamento Presenza Utente (2-3 settimane)

#### 1.1 Mouse Movement Detection
- **File**: `frontend/hooks/usePresenceDetection.ts`
- **Funzionalità**:
  - Rileva movimento del mouse
  - Timeout di inattività (es. 5 minuti = utente assente)
  - Eventi: `user_present`, `user_away`, `user_idle`

#### 1.2 Camera Detection (Opzionale)
- **File**: `frontend/hooks/useCameraPresence.ts`
- **Funzionalità**:
  - Usa WebRTC per accedere alla camera
  - Face detection usando MediaPipe o TensorFlow.js
  - Eventi: `face_detected`, `no_face_detected`
  - Richiede permesso utente

#### 1.3 Keyboard Activity Detection
- **File**: `frontend/hooks/useKeyboardActivity.ts`
- **Funzionalità**:
  - Rileva pressione tasti
  - Timeout di inattività
  - Eventi: `keyboard_active`, `keyboard_idle`

#### 1.4 Presence Service
- **File**: `frontend/services/presenceService.ts`
- **Funzionalità**:
  - Combina tutti i rilevatori di presenza
  - Stato aggregato: `present`, `away`, `idle`
  - Pubblica eventi al backend via WebSocket o SSE

---

### Fase 2: Avatar Component (2-3 settimane)

#### 2.1 Avatar Base Component
- **File**: `frontend/components/Avatar.tsx`
- **Funzionalità**:
  - Avatar animato (Lottie, CSS animations, o SVG)
  - Stati: `idle`, `listening`, `thinking`, `speaking`, `notifying`
  - Posizionamento: corner, floating, sidebar

#### 2.2 Avatar Animations
- **File**: `frontend/components/Avatar/animations.ts`
- **Animazioni**:
  - `wave`: Saluta quando utente torna
  - `notification`: Indica nuova notifica
  - `thinking`: Mostra che sta processando
  - `speaking`: Animazione mentre parla

#### 2.3 Avatar Personality
- **File**: `frontend/components/Avatar/personality.ts`
- **Funzionalità**:
  - Personalità configurabile (amichevole, professionale, ecc.)
  - Reazioni diverse a eventi
  - Memoria delle interazioni precedenti

---

### Fase 3: Notification Integration (1-2 settimane)

#### 3.1 Avatar Notification Display
- **File**: `frontend/components/Avatar/NotificationBubble.tsx`
- **Funzionalità**:
  - Bubble sopra l'avatar con preview notifica
  - Animazione di attenzione quando nuova notifica
  - Click per aprire notifica completa

#### 3.2 Smart Notification Timing
- **File**: `frontend/services/smartNotificationService.ts`
- **Funzionalità**:
  - Mostra notifiche solo quando utente è presente
  - Raggruppa notifiche simili
  - Priorità basata su urgenza e contesto
  - Delay per notifiche non urgenti

#### 3.3 Notification Preferences
- **File**: `frontend/components/Settings/NotificationPreferences.tsx`
- **Funzionalità**:
  - Configura quando mostrare notifiche
  - Scegli metodi di rilevamento presenza
  - Personalizza comportamento avatar

---

### Fase 4: Backend Integration (1 settimana)

#### 4.1 Presence API
- **File**: `backend/app/api/presence.py`
- **Endpoint**:
  - `POST /api/presence/update` - Aggiorna stato presenza
  - `GET /api/presence/status` - Ottieni stato corrente
  - `WebSocket /api/presence/stream` - Stream eventi presenza

#### 4.2 Notification Queue
- **File**: `backend/app/services/notification_queue.py`
- **Funzionalità**:
  - Coda notifiche in attesa di utente presente
  - Priorità e scheduling
  - Batch notifications quando utente torna

---

## 🏗️ Architettura Proposta

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend                              │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐    ┌──────────────┐                   │
│  │   Avatar     │◄───│  Presence    │                   │
│  │  Component   │    │  Detection   │                   │
│  └──────┬───────┘    └──────┬───────┘                   │
│         │                   │                            │
│         │                   │                            │
│         ▼                   ▼                            │
│  ┌──────────────────────────────────────┐               │
│  │   Smart Notification Service         │               │
│  │   - Timing logic                    │               │
│  │   - Priority management             │               │
│  └──────────────┬───────────────────────┘               │
│                 │                                       │
│                 ▼                                       │
│  ┌──────────────────────────────────────┐               │
│  │   Notification Bell (existing)        │               │
│  └──────────────────────────────────────┘               │
│                                                          │
└──────────────────────┬──────────────────────────────────┘
                       │
                       │ WebSocket / SSE
                       │
┌──────────────────────▼──────────────────────────────────┐
│                    Backend                               │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────────────────────────────┐               │
│  │   Presence API                       │               │
│  │   - Update presence status            │               │
│  │   - Stream presence events            │               │
│  └──────────────┬───────────────────────┘               │
│                 │                                       │
│                 ▼                                       │
│  ┌──────────────────────────────────────┐               │
│  │   Notification Queue                 │               │
│  │   - Queue notifications               │               │
│  │   - Schedule delivery                │               │
│  └──────────────────────────────────────┘               │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## 📋 Dettagli Implementazione

### Presence Detection Hook

```typescript
// frontend/hooks/usePresenceDetection.ts
export function usePresenceDetection() {
  const [presence, setPresence] = useState<'present' | 'away' | 'idle'>('present')
  
  useEffect(() => {
    let idleTimeout: NodeJS.Timeout
    let lastActivity = Date.now()
    
    const updateActivity = () => {
      lastActivity = Date.now()
      setPresence('present')
      clearTimeout(idleTimeout)
      
      idleTimeout = setTimeout(() => {
        setPresence('idle')
      }, 5 * 60 * 1000) // 5 minutes
    }
    
    // Mouse movement
    window.addEventListener('mousemove', updateActivity)
    // Keyboard
    window.addEventListener('keydown', updateActivity)
    // Scroll
    window.addEventListener('scroll', updateActivity)
    
    return () => {
      window.removeEventListener('mousemove', updateActivity)
      window.removeEventListener('keydown', updateActivity)
      window.removeEventListener('scroll', updateActivity)
      clearTimeout(idleTimeout)
    }
  }, [])
  
  return presence
}
```

### Avatar Component Structure

```typescript
// frontend/components/Avatar.tsx
interface AvatarProps {
  presence: 'present' | 'away' | 'idle'
  hasNotifications: boolean
  notificationCount: number
  onNotificationClick: () => void
}

export function Avatar({ presence, hasNotifications, notificationCount, onNotificationClick }: AvatarProps) {
  const [animation, setAnimation] = useState<'idle' | 'wave' | 'notify' | 'thinking'>('idle')
  
  useEffect(() => {
    if (hasNotifications && presence === 'present') {
      setAnimation('notify')
    } else if (presence === 'present') {
      setAnimation('idle')
    }
  }, [hasNotifications, presence])
  
  return (
    <div className="avatar-container">
      <div className={`avatar ${animation}`}>
        {/* Avatar visual */}
      </div>
      {hasNotifications && (
        <NotificationBubble count={notificationCount} onClick={onNotificationClick} />
      )}
    </div>
  )
}
```

---

## 🔧 Configurazione

### Environment Variables

```env
# Presence Detection
PRESENCE_IDLE_TIMEOUT_MS=300000  # 5 minutes
PRESENCE_AWAY_TIMEOUT_MS=900000   # 15 minutes

# Avatar
AVATAR_ENABLED=true
AVATAR_POSITION=corner  # corner, floating, sidebar
AVATAR_PERSONALITY=friendly  # friendly, professional, casual

# Camera Detection (optional)
CAMERA_DETECTION_ENABLED=false
CAMERA_DETECTION_INTERVAL_MS=5000
```

---

## 📊 Metriche e Monitoring

- **Presence Accuracy**: Quanto accurato è il rilevamento presenza
- **Notification Delivery Time**: Tempo tra creazione e visualizzazione
- **User Engagement**: Click-through rate delle notifiche
- **False Positives**: Notifiche mostrate quando utente assente

---

## 🎨 Design Considerations

1. **Non Invasivo**: Avatar discreto, non distrae
2. **Accessibile**: Funziona senza camera/keyboard se necessario
3. **Privacy**: Camera opzionale, richiede permesso esplicito
4. **Performance**: Rilevamento presenza leggero, non impatta performance
5. **Personalizzabile**: Utente può configurare comportamento

---

## 🚧 Limitazioni e Considerazioni

1. **Privacy**: Camera detection richiede permesso utente
2. **Performance**: Face detection può essere pesante
3. **Browser Compatibility**: Alcune API potrebbero non essere disponibili
4. **Battery**: Rilevamento continuo può consumare batteria

---

## ✅ Checklist Implementazione

### Fase 1: Presence Detection
- [ ] Mouse movement detection
- [ ] Keyboard activity detection
- [ ] Idle timeout logic
- [ ] Presence state management
- [ ] Backend API per presenza
- [ ] WebSocket/SSE per sync

### Fase 2: Avatar Component
- [ ] Base avatar component
- [ ] Animazioni base
- [ ] Stati avatar (idle, notify, thinking)
- [ ] Positioning system
- [ ] Responsive design

### Fase 3: Notification Integration
- [ ] Notification bubble
- [ ] Smart timing logic
- [ ] Priority management
- [ ] User preferences UI

### Fase 4: Testing & Polish
- [ ] Unit tests
- [ ] E2E tests
- [ ] Performance optimization
- [ ] Accessibility audit
- [ ] Documentation

---

## 📝 Note

- **Priorità**: Implementare prima presence detection semplice (mouse/keyboard)
- **Camera**: Opzionale, può essere aggiunta dopo
- **Avatar**: Può iniziare semplice (emoji/icona) e evolvere
- **Backward Compatibility**: Sistema deve funzionare anche senza avatar

---

## 🔗 Riferimenti

- [MediaPipe Face Detection](https://google.github.io/mediapipe/solutions/face_detection.html)
- [TensorFlow.js](https://www.tensorflow.org/js)
- [WebRTC API](https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API)
- [Lottie Animations](https://lottiefiles.com/)

