from fastapi import APIRouter, Depends
from typing import Dict, Any, List
from pydantic import BaseModel

from app.core.dependencies import get_mcp_client
from app.core.mcp_client import MCPClient

router = APIRouter()


class ToolCallRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any]


@router.get("/list")
async def list_tools(mcp: MCPClient = Depends(get_mcp_client)):
    """List available MCP tools"""
    tools = await mcp.list_tools()
    return {"tools": tools}


@router.post("/call")
async def call_tool(
    request: ToolCallRequest,
    mcp: MCPClient = Depends(get_mcp_client),
):
    """Call an MCP tool"""
    result = await mcp.call_tool(request.tool_name, request.parameters)
    return {"tool": request.tool_name, "result": result}


@router.get("/browser/navigate")
async def browser_navigate(url: str, mcp: MCPClient = Depends(get_mcp_client)):
    """Navigate to a URL using browser tool"""
    result = await mcp.browser_navigate(url)
    return {"result": result}


@router.get("/browser/search")
async def browser_search(query: str, mcp: MCPClient = Depends(get_mcp_client)):
    """Search the web using browser tool"""
    result = await mcp.browser_search(query)
    return {"result": result}


@router.get("/maps/geocode")
async def maps_geocode(address: str, mcp: MCPClient = Depends(get_mcp_client)):
    """Geocode an address"""
    result = await mcp.maps_geocode(address)
    return {"result": result}


@router.get("/maps/directions")
async def maps_directions(
    origin: str,
    destination: str,
    travel_mode: str = "DRIVE",
    mcp: MCPClient = Depends(get_mcp_client),
):
    """Get directions between two locations"""
    result = await mcp.maps_directions(origin, destination, travel_mode)
    return {"result": result}


@router.get("/papers/arxiv/search")
async def search_arxiv(
    query: str,
    max_results: int = 10,
    mcp: MCPClient = Depends(get_mcp_client),
):
    """Search arXiv papers"""
    result = await mcp.search_arxiv(query, max_results)
    return {"result": result}


@router.get("/papers/semantic/search")
async def search_semantic(
    query: str,
    max_results: int = 10,
    mcp: MCPClient = Depends(get_mcp_client),
):
    """Search Semantic Scholar"""
    result = await mcp.search_semantic(query, max_results)
    return {"result": result}

