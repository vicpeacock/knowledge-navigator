# Piano Gestione Utenti Multi-Tenant

## 📋 Indice
1. [Architettura Autenticazione](#architettura-autenticazione)
2. [Database Schema](#database-schema)
3. [Backend API](#backend-api)
4. [Frontend UI](#frontend-ui)
5. [Flussi Utente](#flussi-utente)
6. [Sicurezza](#sicurezza)

---

## Architettura Autenticazione

### Opzione A: Solo API Keys (Attuale)
**Quando usare**: Integrazioni, automazioni, API-first

**Flusso**:
```
1. Admin crea utente → genera API key
2. Utente usa API key → sistema identifica tenant + user
3. Nessun login form
```

**Vantaggi**:
- ✅ Semplice
- ✅ Già implementato (parzialmente)
- ✅ Perfetto per automazioni

**Svantaggi**:
- ❌ Nessun login tradizionale
- ❌ Gestione password non necessaria

---

### Opzione B: Login + JWT (Raccomandato)
**Quando usare**: Applicazioni web con utenti finali

**Flusso**:
```
1. Utente fa login → email + password
2. Sistema verifica → genera JWT token
3. JWT contiene: user_id + tenant_id
4. Frontend usa JWT → tutte le richieste includono token
```

**Vantaggi**:
- ✅ Esperienza utente standard
- ✅ Sicurezza migliore
- ✅ Supporto ruoli/permessi
- ✅ Refresh tokens

**Svantaggi**:
- ❌ Più complesso da implementare

---

## Database Schema

### Modifiche al Modello User

```python
class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"))
    email = Column(String(255), nullable=False)
    name = Column(String(255), nullable=True)
    
    # NUOVO: Password (hashato con bcrypt)
    password_hash = Column(String(255), nullable=True)  # NULL per utenti API-only
    
    # NUOVO: Ruoli e permessi
    role = Column(String(50), default="user")  # admin, user, viewer
    permissions = Column(JSONB, default={})  # Permessi granulari
    
    # NUOVO: Email verification
    email_verified = Column(Boolean, default=False)
    email_verification_token = Column(String(255), nullable=True)
    
    # NUOVO: Password reset
    password_reset_token = Column(String(255), nullable=True)
    password_reset_expires = Column(DateTime(timezone=True), nullable=True)
    
    # NUOVO: Session tracking
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    last_login_ip = Column(String(45), nullable=True)  # IPv6 support
    
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user_metadata = Column("metadata", JSONB, default={})
```

### Nuova Tabella: UserSessions (per refresh tokens)

```python
class UserSession(Base):
    """Sessioni utente per refresh tokens"""
    __tablename__ = "user_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    
    refresh_token_hash = Column(String(255), nullable=False, unique=True)
    device_info = Column(String(255), nullable=True)  # Browser, device, etc.
    ip_address = Column(String(45), nullable=True)
    
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), server_default=func.now())
    
    active = Column(Boolean, default=True)  # Per revocare sessioni
```

---

## Backend API

### Endpoint Autenticazione

#### 1. Registrazione Utente
```python
POST /api/v1/auth/register
Body: {
    "email": "user@example.com",
    "password": "secure_password",
    "name": "John Doe",
    "tenant_id": "..."  # Opzionale se admin crea utente
}
Response: {
    "user_id": "...",
    "email": "user@example.com",
    "email_verification_required": true
}
```

#### 2. Login
```python
POST /api/v1/auth/login
Body: {
    "email": "user@example.com",
    "password": "secure_password"
}
Response: {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_in": 3600,
    "user": {
        "id": "...",
        "email": "user@example.com",
        "name": "John Doe",
        "tenant_id": "...",
        "role": "user"
    }
}
```

#### 3. Refresh Token
```python
POST /api/v1/auth/refresh
Body: {
    "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
Response: {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "expires_in": 3600
}
```

#### 4. Logout
```python
POST /api/v1/auth/logout
Headers: {
    "Authorization": "Bearer <access_token>"
}
Response: {
    "message": "Logged out successfully"
}
```

#### 5. Verifica Email
```python
GET /api/v1/auth/verify-email?token=<verification_token>
Response: {
    "message": "Email verified successfully"
}
```

#### 6. Password Reset Request
```python
POST /api/v1/auth/password-reset/request
Body: {
    "email": "user@example.com"
}
Response: {
    "message": "Password reset email sent"
}
```

#### 7. Password Reset Confirm
```python
POST /api/v1/auth/password-reset/confirm
Body: {
    "token": "<reset_token>",
    "new_password": "new_secure_password"
}
Response: {
    "message": "Password reset successfully"
}
```

### Endpoint Gestione Utenti (Admin)

#### 1. Lista Utenti (del tenant corrente)
```python
GET /api/v1/users
Headers: {
    "Authorization": "Bearer <token>"
}
Query: ?role=user&active=true
Response: [
    {
        "id": "...",
        "email": "user@example.com",
        "name": "John Doe",
        "role": "user",
        "active": true,
        "last_login_at": "2025-01-15T10:00:00Z",
        "created_at": "2025-01-01T00:00:00Z"
    }
]
```

#### 2. Crea Utente (Admin)
```python
POST /api/v1/users
Headers: {
    "Authorization": "Bearer <admin_token>"
}
Body: {
    "email": "newuser@example.com",
    "name": "New User",
    "password": "temporary_password",
    "role": "user",
    "send_invitation_email": true
}
Response: {
    "id": "...",
    "email": "newuser@example.com",
    "name": "New User",
    "role": "user",
    "email_verification_required": true
}
```

#### 3. Aggiorna Utente
```python
PUT /api/v1/users/{user_id}
Headers: {
    "Authorization": "Bearer <token>"
}
Body: {
    "name": "Updated Name",
    "role": "admin",
    "active": true
}
```

#### 4. Disattiva Utente
```python
DELETE /api/v1/users/{user_id}
Headers: {
    "Authorization": "Bearer <admin_token>"
}
Response: {
    "message": "User deactivated"
}
```

#### 5. Cambia Password (Utente)
```python
POST /api/v1/users/me/change-password
Headers: {
    "Authorization": "Bearer <token>"
}
Body: {
    "current_password": "old_password",
    "new_password": "new_secure_password"
}
```

---

## Frontend UI

### Struttura Pagine

```
frontend/app/
├── auth/
│   ├── login/
│   │   └── page.tsx          # Pagina login
│   ├── register/
│   │   └── page.tsx          # Pagina registrazione
│   ├── verify-email/
│   │   └── page.tsx          # Verifica email
│   ├── password-reset/
│   │   ├── request/
│   │   │   └── page.tsx      # Richiesta reset password
│   │   └── confirm/
│   │       └── page.tsx      # Conferma reset password
│   └── layout.tsx            # Layout auth (no sidebar)
│
├── admin/
│   └── users/
│       ├── page.tsx          # Lista utenti (admin)
│       ├── [id]/
│       │   └── page.tsx      # Dettaglio/editing utente
│       └── new/
│           └── page.tsx      # Crea nuovo utente
│
└── settings/
    └── profile/
        └── page.tsx          # Profilo utente (cambia password, etc.)
```

### Componenti

#### 1. AuthContext (Gestione stato autenticazione)
```typescript
// frontend/contexts/AuthContext.tsx
interface AuthContextType {
    user: User | null;
    token: string | null;
    login: (email: string, password: string) => Promise<void>;
    logout: () => Promise<void>;
    refreshToken: () => Promise<void>;
    isAuthenticated: boolean;
    isLoading: boolean;
}
```

#### 2. LoginForm
```typescript
// frontend/components/auth/LoginForm.tsx
- Email input
- Password input
- "Remember me" checkbox
- "Forgot password?" link
- Submit button
- Error messages
```

#### 3. UserList (Admin)
```typescript
// frontend/components/admin/UserList.tsx
- Tabella con: Email, Nome, Ruolo, Ultimo accesso, Stato
- Filtri: Ruolo, Stato attivo/inattivo
- Azioni: Modifica, Disattiva, Reimposta password
- Pulsante "Crea nuovo utente"
```

#### 4. UserForm (Crea/Modifica)
```typescript
// frontend/components/admin/UserForm.tsx
- Email input (disabled se editing)
- Nome input
- Ruolo select (admin, user, viewer)
- Password input (solo se nuovo utente)
- Checkbox "Invia email di invito"
- Checkbox "Attivo"
- Pulsanti: Salva, Annulla
```

#### 5. ProfileSettings
```typescript
// frontend/components/settings/ProfileSettings.tsx
- Informazioni utente (read-only)
- Cambio password form
- Impostazioni notifiche
- Gestione API keys personali
```

### Interceptor Axios (JWT)

```typescript
// frontend/lib/api.ts
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
        config.headers['Authorization'] = `Bearer ${token}`;
    }
    
    // Multi-tenant: aggiungi tenant_id se disponibile
    const tenantId = localStorage.getItem('tenant_id');
    if (tenantId) {
        config.headers['X-Tenant-ID'] = tenantId;
    }
    
    return config;
});

// Refresh token automatico su 401
api.interceptors.response.use(
    (response) => response,
    async (error) => {
        if (error.response?.status === 401) {
            // Prova refresh token
            const refreshToken = localStorage.getItem('refresh_token');
            if (refreshToken) {
                try {
                    const { data } = await api.post('/api/v1/auth/refresh', {
                        refresh_token: refreshToken
                    });
                    localStorage.setItem('access_token', data.access_token);
                    // Riprova richiesta originale
                    return api.request(error.config);
                } catch {
                    // Refresh fallito, logout
                    localStorage.removeItem('access_token');
                    localStorage.removeItem('refresh_token');
                    window.location.href = '/auth/login';
                }
            }
        }
        return Promise.reject(error);
    }
);
```

---

## Flussi Utente

### Flusso 1: Registrazione Nuovo Utente

```
1. Utente visita /auth/register
2. Compila form: email, password, nome
3. Submit → POST /api/v1/auth/register
4. Backend:
   - Crea utente (tenant_id dal contesto o default)
   - Hash password (bcrypt)
   - Genera email verification token
   - Invia email di verifica
5. Frontend mostra: "Controlla la tua email"
6. Utente clicca link email → /auth/verify-email?token=...
7. Backend verifica token → attiva account
8. Redirect a /auth/login
```

### Flusso 2: Login

```
1. Utente visita /auth/login
2. Compila: email, password
3. Submit → POST /api/v1/auth/login
4. Backend:
   - Verifica email/password
   - Genera JWT access token (15 min)
   - Genera refresh token (7 giorni)
   - Salva sessione in user_sessions
   - Aggiorna last_login_at
5. Frontend:
   - Salva tokens in localStorage
   - Salva user info in context
   - Redirect a / (homepage)
```

### Flusso 3: Admin Crea Utente

```
1. Admin va a /admin/users
2. Clicca "Crea nuovo utente"
3. Compila form: email, nome, ruolo, password temporanea
4. Checkbox "Invia email di invito"
5. Submit → POST /api/v1/users
6. Backend:
   - Crea utente con tenant_id dell'admin
   - Hash password
   - Se "send_invitation_email": invia email con link setup
7. Frontend mostra successo
8. Utente riceve email → clicca link → setup password
```

### Flusso 4: Password Reset

```
1. Utente clicca "Password dimenticata?" su login
2. Va a /auth/password-reset/request
3. Inserisce email
4. Submit → POST /api/v1/auth/password-reset/request
5. Backend:
   - Genera reset token (scadenza 1 ora)
   - Invia email con link
6. Utente clicca link → /auth/password-reset/confirm?token=...
7. Inserisce nuova password
8. Submit → POST /api/v1/auth/password-reset/confirm
9. Backend verifica token → aggiorna password
10. Redirect a /auth/login
```

---

## Sicurezza

### Password Hashing
- **Algoritmo**: bcrypt (cost factor 12)
- **Salt**: Automatico (bcrypt gestisce)
- **Storage**: Solo hash, mai password in chiaro

### JWT Tokens
- **Algoritmo**: HS256 (HMAC-SHA256)
- **Access Token**: 15 minuti (scadenza breve)
- **Refresh Token**: 7 giorni (scadenza lunga)
- **Payload**: `{ user_id, tenant_id, email, role, exp, iat }`
- **Storage**: localStorage (frontend)

### Validazione
- ✅ Email formato valido
- ✅ Password: minimo 8 caratteri, almeno 1 maiuscola, 1 numero
- ✅ Rate limiting su login (max 5 tentativi/15 min)
- ✅ Account lockout dopo N tentativi falliti
- ✅ HTTPS obbligatorio in produzione

### Ruoli e Permessi

```typescript
enum UserRole {
    ADMIN = 'admin',      // Gestione utenti, configurazione tenant
    USER = 'user',        // Uso normale dell'app
    VIEWER = 'viewer'      // Solo lettura
}

interface Permissions {
    sessions: {
        create: boolean;
        read: boolean;
        update: boolean;
        delete: boolean;
    };
    users: {
        create: boolean;
        read: boolean;
        update: boolean;
        delete: boolean;
    };
    // ... altri permessi
}
```

---

## Implementazione Step-by-Step

### Step 1: Database
- [ ] Aggiungere `password_hash` a `users`
- [ ] Aggiungere `role`, `permissions` a `users`
- [ ] Aggiungere campi email verification
- [ ] Creare tabella `user_sessions`
- [ ] Migration Alembic

### Step 2: Backend - Auth
- [ ] Installare `python-jose[cryptography]` per JWT
- [ ] Installare `bcrypt` per password hashing
- [ ] Creare `app/core/auth.py` (hash, verify password)
- [ ] Creare `app/core/jwt.py` (genera, verifica JWT)
- [ ] Creare `app/api/auth.py` (endpoint login, register, etc.)

### Step 3: Backend - Users
- [ ] Creare `app/api/users.py` (CRUD utenti)
- [ ] Dependency `get_current_user()` (verifica JWT)
- [ ] Dependency `require_role()` (verifica permessi)
- [ ] Filtri tenant_id su tutte le query

### Step 4: Frontend - Auth
- [ ] Creare `contexts/AuthContext.tsx`
- [ ] Creare pagine: login, register, password-reset
- [ ] Aggiornare `api.ts` con JWT interceptor
- [ ] Proteggere route con middleware

### Step 5: Frontend - Admin
- [ ] Creare `/admin/users` (lista)
- [ ] Creare `/admin/users/new` (crea)
- [ ] Creare `/admin/users/[id]` (modifica)
- [ ] Componenti: UserList, UserForm

### Step 6: Testing
- [ ] Test backend: login, register, JWT
- [ ] Test frontend: flussi completi
- [ ] Test sicurezza: password hash, token expiration
- [ ] Test multi-tenant: isolamento utenti

---

## Domande da Decidere

1. **Registrazione pubblica?**
   - ✅ Sì: chiunque può registrarsi → tenant default
   - ❌ No: solo admin crea utenti

2. **Email verification obbligatoria?**
   - ✅ Sì: account non attivo finché email non verificata
   - ❌ No: account attivo subito

3. **Ruoli predefiniti o custom?**
   - ✅ Predefiniti: admin, user, viewer
   - ❌ Custom: permessi granulari per tenant

4. **API Keys per utente o solo tenant?**
   - ✅ Per utente: ogni utente può avere API keys personali
   - ❌ Solo tenant: API keys condivise

---

## Raccomandazioni

1. **Inizia con Login + JWT** (Approccio B)
   - Esperienza utente migliore
   - Più sicuro
   - Scalabile per ruoli/permessi

2. **Mantieni API Keys** per integrazioni
   - Utili per automazioni
   - Possono coesistere con JWT

3. **Implementa step-by-step**
   - Step 1-2: Backend auth base
   - Step 3: Frontend login
   - Step 4: Admin users
   - Step 5: Features avanzate

4. **Sicurezza first**
   - Password hashing obbligatorio
   - Rate limiting su login
   - HTTPS in produzione
   - Validazione input rigorosa

