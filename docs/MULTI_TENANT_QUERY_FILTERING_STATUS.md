# Multi-Tenant Query Filtering - Status

Questo documento traccia lo stato delle modifiche alle query per filtrare per `tenant_id`.

## Pattern da Applicare

Per ogni endpoint che accede al database:

1. **Aggiungere dependency**: `tenant_id: UUID = Depends(get_tenant_id)`
2. **Filtrare query**: Aggiungere `.where(Model.tenant_id == tenant_id)` a tutte le query
3. **Validare ownership**: Quando si accede a una risorsa per ID, verificare che appartenga al tenant
4. **Assegnare tenant_id**: Quando si crea una risorsa, assegnare `tenant_id`

## Endpoint Modificati ✅

### `/api/sessions` (backend/app/api/sessions.py)

- [x] `GET /` - `list_sessions()` - Filtra per tenant_id
- [x] `POST /` - `create_session()` - Assegna tenant_id
- [x] `GET /{session_id}` - `get_session()` - Filtra per tenant_id
- [x] `PUT /{session_id}` - `update_session()` - Filtra per tenant_id
- [x] `POST /{session_id}/archive` - `archive_session()` - Filtra per tenant_id e messages

## Endpoint da Modificare ⏳

### `/api/sessions` (backend/app/api/sessions.py)

- [ ] `DELETE /{session_id}` - `delete_session()` - Linea ~340
- [ ] `GET /{session_id}/messages` - `get_messages()` - Linea ~380
- [ ] `POST /{session_id}/messages` - `create_message()` - Linea ~400
- [ ] `GET /{session_id}/memory` - `get_session_memory()` - Linea ~1550
- [ ] `POST /{session_id}/chat` - `chat()` - Linea ~630
  - Query SessionModel (linea ~655)
  - Query MessageModel (linea ~672)
- [ ] Altri endpoint che usano `select(SessionModel)` o `select(MessageModel)`

### `/api/files` (backend/app/api/files.py)

- [ ] Tutti gli endpoint che accedono a `File` model
- [ ] Verificare che `session_id` appartenga al tenant

### `/api/memory` (backend/app/api/memory.py)

- [ ] Tutti gli endpoint che accedono a `MemoryMedium`, `MemoryLong`, `MemoryShort`
- [ ] Filtrare per tenant_id

### `/api/notifications` (backend/app/api/notifications.py)

- [ ] Tutti gli endpoint che accedono a `Notification` model
- [ ] Filtrare per tenant_id

### `/api/integrations/*` (backend/app/api/integrations/)

- [ ] Tutti gli endpoint che accedono a `Integration` model
- [ ] Filtrare per tenant_id

## Note Importanti

1. **Backward Compatibility**: Tutti gli endpoint devono funzionare senza header `X-Tenant-ID` (usa default tenant)
2. **Security**: Mai esporre dati di altri tenant
3. **Performance**: Gli index su `tenant_id` sono già creati dalle migration
4. **Testing**: Testare isolamento dati con 2 tenant diversi

## Pattern di Codice

### Query con filtro tenant_id

```python
# PRIMA
result = await db.execute(
    select(SessionModel).where(SessionModel.id == session_id)
)

# DOPO
result = await db.execute(
    select(SessionModel).where(
        SessionModel.id == session_id,
        SessionModel.tenant_id == tenant_id
    )
)
```

### Creazione con tenant_id

```python
# PRIMA
session = SessionModel(**session_dict)

# DOPO
session_dict['tenant_id'] = tenant_id
session = SessionModel(**session_dict)
```

### Dependency injection

```python
# PRIMA
async def endpoint(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
):

# DOPO
async def endpoint(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant_id: UUID = Depends(get_tenant_id),
):
```

---

*Ultimo aggiornamento: 2025-01-XX*

