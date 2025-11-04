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
    """
    Call an MCP tool dynamically
    
    This endpoint calls any tool discovered from the MCP server.
    Use /list to see available tools and their schemas.
    """
    result = await mcp.call_tool(request.tool_name, request.parameters)
    return {"tool": request.tool_name, "result": result}

