# LangGraph Orchestration Plan

## Objective
Refactor the chat pipeline onto LangGraph so that message handling becomes an explicit graph with modular agents (Main, Integrity, Knowledge, Notifications, etc.), enabling parallelism and clearer state management.

## Current State Summary
- `langgraph_app.py` defines a minimal `event_handler -> orchestrator -> main_agent` pipeline.
- `main_agent` node wraps the legacy `_chat` flow (`run_main_agent_pipeline`).
- Feature flag `use_langgraph_prototype` routes `/chat` requests through the graph.

## Target Graph (Phase 1)
```text
entry(event_handler)
  -> orchestrator
      -> tool_loop (subgraph)
          -> main_agent
          -> knowledge_agent (async, conditional)
          -> integrity_agent (async, conditional)
          -> notification_collector
      -> response_formatter -> END
```

### Node Responsibilities
- **event_handler**: validate request, enrich with session metadata, emit initial state.
- **orchestrator**: decide graph branches based on request context (force_web_search, follow-up, etc.).
- **tool_loop**: repeated subgraph managing LLM tool selection/execution until completion (LangGraph `While` pattern).
- **main_agent**: call chat LLM with current context & tool results, produce assistant response chunk.
- **knowledge_agent**: schedule auto-learning (ConversationLearner) for user message/assistant reply.
- **integrity_agent**: spawn contradiction check (BackgroundAgent) for user message + new knowledge.
- **notification_collector**: gather `NotificationService` outputs and merge into response state.
- **response_formatter**: consolidate final response, notifications, tool traces.

### State Schema (`TypedDict`)
```python
class LangGraphState(TypedDict, total=False):
    session_id: UUID
    request: ChatRequest
    db: AsyncSession
    ollama: OllamaClient
    session_context: list[dict[str, str]]
    retrieved_memory: list[str]
    memory_used: dict[str, Any]
    messages: list[BaseMessage]
    tool_calls: list[ToolCall]
    tool_results: list[dict[str, Any]]
    notifications: list[dict[str, Any]]
    response: str
    done: bool
```
- `messages`: chronological chat history for LangGraph message passing.
- `tool_calls` / `tool_results`: accumulate per iteration.
- `notifications`: gathered from NotificationService for UI display.
- `done`: control flag for tool loop termination.

## Migration Steps
1. **Graph Definition**
   - Update `langgraph_app.py`: define state schema, register nodes/states.
   - Introduce LangGraph `StateGraph` with loops (while) using named edges.
2. **Node Stubs**
   - Implement async stubs for `tool_loop`, `knowledge_agent`, `integrity_agent`, `notification_collector`, `response_formatter`.
   - Keep logic minimal (logging + pass-through) to validate wiring.
3. **Incremental Porting**
   - Move tool execution logic from `ToolManager`/legacy loop into `tool_loop`.
   - Move knowledge extraction scheduling into `knowledge_agent` node.
   - Route contradiction check through `integrity_agent`.
   - Collect notifications post-loop via `notification_collector`.
4. **State Convergence**
   - Ensure legacy `run_main_agent_pipeline` returns state updates (response, tool traces) and stops mutating DB directly where necessary.
   - Provide helper utils for message/tool state serialization.
5. **Testing**
   - Add `tests/test_langgraph_pipeline.py` covering: no-tool chat, tool usage, knowledge extraction, contradiction alert.
   - Manual smoke test via frontend toggling `use_langgraph_prototype`.
6. **Cleanup & Flag Flip**
   - When graph is parity-complete, replace legacy flow with LangGraph by default.
   - Remove redundant logic from `sessions.py` once new graph stable.

## Open Questions
- Do we want `knowledge_agent`/`integrity_agent` to run in parallel (background tasks) or sequential nodes? Initial plan: sequential nodes with async tasks to keep pipeline deterministic.
- Notification prioritization currently in `sessions.py`; may need dedicated `notification_router` logic inside graph.
- Monitoring/metrics: evaluate LangGraph instrumentation hooks once pipeline stabilizes.

## Immediate Next Actions
1. Update `langgraph_app.py` to declare new state schema and register node placeholders.
2. Implement node stubs returning pass-through state for the new components.
3. Add unit test verifying graph compilation and basic execution (no tools) still works.
