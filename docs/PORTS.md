# Porte Utilizzate - Knowledge Navigator

## Porte Configurate

| Servizio | Porta | Note |
|----------|-------|------|
| **PostgreSQL** | 5432 | Database principale (se occupata, cambiare a 5433) |
| **ChromaDB** | 8001 | Database vettoriale (cambiata da 8000 per evitare conflitto) |
| **Backend FastAPI** | 8000 | API server principale |
| **Frontend Next.js** | 3003 | Interface web (cambiata da 3000 per OpenWebUI, 3001 occupata) |
| **Ollama** | 11434 | LLM provider (già in uso dall'utente) |
| **MCP Gateway** | 3002 | Gateway per MCP tools (cambiata da 3000 per evitare conflitto) |

## Verifica Porte in Uso

Per verificare quali porte sono già in uso:

```bash
# Controlla porte specifiche
lsof -i -P -n | grep LISTEN | grep -E ':(3000|3002|5432|8000|8001|11434)'

# Controlla tutte le porte in ascolto
lsof -i -P -n | grep LISTEN
```

## Modificare le Porte

Se devi cambiare una porta:

1. **PostgreSQL**: Modifica `docker-compose.yml` → `postgres.ports` e `backend/app/core/config.py` → `postgres_port`
2. **ChromaDB**: Modifica `docker-compose.yml` → `chromadb.ports` e `backend/app/core/config.py` → `chromadb_port`
3. **Backend**: Modifica il comando uvicorn: `--port <nuova_porta>` e `.env` → `NEXT_PUBLIC_API_URL`
4. **Frontend**: Modifica `package.json` → script `dev`: `next dev -p <nuova_porta>`
5. **MCP Gateway**: Modifica `backend/app/core/config.py` → `mcp_gateway_url`

## Porte Alternative Suggerite

Se una porta è occupata, usa queste alternative:

- PostgreSQL: 5432 → 5433, 5434
- ChromaDB: 8001 → 8002, 8003
- Backend: 8000 → 8080, 8888
- Frontend: 3000 → 3001, 3003, 3004
- MCP Gateway: 3002 → 3003, 3004

## ⚠️ Note

- **Porta 3000**: Occupata da OpenWebUI (non modificare)
- **Porta 3003**: Frontend Next.js Knowledge Navigator (3001 occupata)
- **Porta 11434**: Ollama già in uso (corretto)
- **Porte 5432, 8000, 8001, 3002**: Verificare se libere prima di avviare

