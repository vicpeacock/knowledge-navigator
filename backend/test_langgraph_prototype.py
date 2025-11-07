import pytest

from app.agents.langgraph_prototype import run_prototype_event


@pytest.mark.asyncio
async def test_langgraph_prototype_generates_response():
    state = await run_prototype_event("Ciao, sono un test")

    assert "response" in state
    assert "LangGraph prototype" in state["response"]
    assert state["messages"][-1]["content"] == "Ciao, sono un test"

