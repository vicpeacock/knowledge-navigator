from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from app.core.dependencies import get_mcp_client
from app.core.mcp_client import MCPClient

router = APIRouter()


class WebSearchRequest(BaseModel):
    query: str
    max_results: Optional[int] = 5


class WebNavigateRequest(BaseModel):
    url: str


@router.post("/search")
async def web_search(
    request: WebSearchRequest,
    mcp: MCPClient = Depends(get_mcp_client),
):
    """
    Perform web search using MCP browser tool
    
    Note: This uses the dynamically discovered browser_search tool from MCP.
    If the tool is not available, this will fail.
    """
    # Dynamically call browser_search tool (name may vary)
    # First try common names
    tool_names = ["browser_search", "mcp_browser_search", "search"]
    for tool_name in tool_names:
        try:
            result = await mcp.call_tool(tool_name, {"query": request.query})
            return {"query": request.query, "result": result}
        except Exception:
            continue
    
    # If no tool found, list available tools and suggest
    tools = await mcp.list_tools()
    browser_tools = [t for t in tools if isinstance(t, dict) and "search" in t.get("name", "").lower()]
    if browser_tools:
        tool_name = browser_tools[0].get("name")
        result = await mcp.call_tool(tool_name, {"query": request.query})
        return {"query": request.query, "result": result}
    
    raise ValueError(f"No web search tool found. Available tools: {[t.get('name') for t in tools[:10]]}")


@router.post("/navigate")
async def web_navigate(
    request: WebNavigateRequest,
    mcp: MCPClient = Depends(get_mcp_client),
):
    """
    Navigate to a URL using MCP browser tool
    
    Note: This uses the dynamically discovered browser_navigate tool from MCP.
    If the tool is not available, this will fail.
    """
    # Dynamically call browser_navigate tool (name may vary)
    tool_names = ["browser_navigate", "mcp_browser_navigate", "navigate"]
    for tool_name in tool_names:
        try:
            result = await mcp.call_tool(tool_name, {"url": request.url})
            return {"url": request.url, "result": result}
        except Exception:
            continue
    
    # If no tool found, list available tools and suggest
    tools = await mcp.list_tools()
    browser_tools = [t for t in tools if isinstance(t, dict) and "navigate" in t.get("name", "").lower() and "back" not in t.get("name", "").lower()]
    if browser_tools:
        tool_name = browser_tools[0].get("name")
        result = await mcp.call_tool(tool_name, {"url": request.url})
        return {"url": request.url, "result": result}
    
    raise ValueError(f"No navigation tool found. Available tools: {[t.get('name') for t in tools[:10]]}")

