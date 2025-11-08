# Test Suite

- `backend/unit/` – Test automatici eseguiti regolarmente con pytest.
- `backend/langgraph/` – Test dedicati alla pipeline LangGraph e al planner.
- `backend/manual/` – Script di debug/semi-manuale (tutti contrassegnati con `pytest.skip`).

Esegui ad esempio:

```bash
PYTHONPATH=backend pytest tests/backend/langgraph
```
