# Main Agent Planning Improvements

## Pain Points (User Feedback)
1. **Forced Web Search abuse**: when the frontend toggle is active, every message triggers a web search even for short confirmations ("sì, grazie"), producing irrelevant answers.
2. **Lack of multi-step planning**: the agent fails tasks requiring sequencing (e.g. "cerca sul web info sul mittente dell'ultimo messaggio") and instead mixes web search with unrelated suggestions.
3. **No follow-up execution**: after the assistant asks for confirmation and user replies "sì", nothing happens; the agent restarts from scratch.

## Goals
- Introduce an explicit planning stage before tool execution.
- Store and resume pending plans across messages.
- Apply smarter gating to the "force web search" flag.

## Proposed Flow
1. **Message Classification**
   - Detect acknowledgement/confirmation messages via regex / prompt ("ok", "va bene", "sì" ...).
   - Detect if the current message should reuse an existing plan.
2. **Plan Generation**
   - New function `generate_plan(state)` using LLM tool-free call with a JSON schema (max 5 steps).
   - A plan step schema: `{ "id": int, "description": str, "tool": Optional[str], "status": "pending|complete" }`.
   - Only generate plan if message implies multi-step task OR there is no pending plan.
3. **Plan Storage**
   - Store serialized plan in `SessionModel.session_metadata["pending_plan"]` with pointer to current step.
   - Include `plan_origin_message_id` to reference the request that generated it.
4. **Execution Loop**
   - For each pending step until completion:
     - If step specifies `tool`, call `ToolManager` (via existing tool loop) with targeted parameters.
     - Otherwise, send instruction to LLM to produce partial response / request additional info.
   - After each step, update plan status, persist metadata, and append results to LangGraph state (`tool_results`).
5. **Confirmation Handling**
   - If message is acknowledgement and there is a pending plan, skip plan generation and resume from next pending step.
   - If no plan remains, treat message as new request.
6. **Force Web Search Heuristics**
   - Use web search automatically only when plan/LLM selects it, or when the message explicitly asks for web information.
   - Override `force_web_search` for acknowledgement messages or when the text is short (< 15 chars) and lacks keywords.
7. **Response Formatting**
   - After plan completion, produce final answer summarizing steps taken; include tool evidence.

## Implementation Steps
1. Extend `LangGraphChatState` with `plan` and `current_step` fields.
2. Update `run_langgraph_chat` + `sessions.py` to load/save plan metadata.
3. Implement `detect_acknowledgement(message: str) -> bool` helper.
4. Add `generate_plan` helper (LLM call) and integrate in `tool_loop_node`.
5. Modify tool loop to iterate over plan steps before default ReAct-style calls.
6. Update frontend toggle semantics? (backend heuristics only for now).
7. Tests:
   - Unit test for `detect_acknowledgement`.
   - Simulated end-to-end test with mocked plan returning multi-step instructions.
   - Regression test ensuring short confirmations do not trigger web search.

## Open Questions
- Where to persist partial tool outputs per step (likely `plan_step_results` in metadata).
- How to limit plan generation cost (cache for identical requests?).
- Interaction with future Integrity/Knowledge nodes (plan should note if knowledge extraction needed).
