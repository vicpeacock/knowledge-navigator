import httpx
from typing import Dict, Any, Optional, List
from app.core.config import settings
import json


class MCPClient:
    """
    Client for Docker MCP Gateway
    Provides access to MCP tools like browser, maps, academic papers, etc.
    """
    
    def __init__(self):
        self.base_url = settings.mcp_gateway_url
        self.client = httpx.AsyncClient(timeout=60.0)

    async def call_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Call an MCP tool
        
        Args:
            tool_name: Name of the MCP tool (e.g., 'browser_navigate', 'maps_geocode')
            parameters: Parameters for the tool
            
        Returns:
            Result from the tool
        """
        try:
            # Try direct tool call endpoint
            response = await self.client.post(
                f"{self.base_url}/mcp/tools/{tool_name}",
                json=parameters,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            # Fallback to generic MCP protocol endpoint
            payload = {
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": parameters,
                },
            }
            response = await self.client.post(
                f"{self.base_url}/mcp",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            return result.get("result", {})

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available MCP tools"""
        try:
            response = await self.client.get(f"{self.base_url}/mcp/tools")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            # Fallback
            payload = {"method": "tools/list"}
            response = await self.client.post(
                f"{self.base_url}/mcp",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            return result.get("result", {}).get("tools", [])

    # Browser tools
    async def browser_navigate(self, url: str) -> Dict[str, Any]:
        """Navigate to a URL"""
        return await self.call_tool("browser_navigate", {"url": url})

    async def browser_search(self, query: str) -> Dict[str, Any]:
        """Search the web"""
        return await self.call_tool("browser_search", {"query": query})

    # Maps tools
    async def maps_geocode(self, address: str) -> Dict[str, Any]:
        """Geocode an address"""
        return await self.call_tool("maps_geocode", {"address": address})

    async def maps_directions(
        self,
        origin: str,
        destination: str,
        travel_mode: str = "DRIVE",
    ) -> Dict[str, Any]:
        """Get directions between two locations"""
        return await self.call_tool(
            "maps_directions",
            {
                "origin": origin,
                "destination": destination,
                "travelMode": travel_mode,
            },
        )

    # Academic tools
    async def search_arxiv(self, query: str, max_results: int = 10) -> Dict[str, Any]:
        """Search arXiv papers"""
        return await self.call_tool(
            "search_arxiv",
            {"query": query, "max_results": max_results},
        )

    async def search_semantic(self, query: str, max_results: int = 10) -> Dict[str, Any]:
        """Search Semantic Scholar"""
        return await self.call_tool(
            "search_semantic",
            {"query": query, "max_results": max_results},
        )

    async def download_arxiv(self, paper_id: str) -> Dict[str, Any]:
        """Download arXiv paper"""
        return await self.call_tool("download_arxiv", {"paper_id": paper_id})

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

