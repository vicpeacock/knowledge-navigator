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
    """Perform web search"""
    result = await mcp.browser_search(request.query)
    return {"query": request.query, "result": result}


@router.post("/navigate")
async def web_navigate(
    request: WebNavigateRequest,
    mcp: MCPClient = Depends(get_mcp_client),
):
    """Navigate to a URL"""
    result = await mcp.browser_navigate(request.url)
    return {"url": request.url, "result": result}

