"""
Read-only MCP helpers for agent alerts / logs (dashboard AgentAlert model).
"""
from mcp_server import client


async def list_agent_alerts(page_size: int = 60) -> list:
    """Recent agent alerts (severity, message, church)."""
    params = {"page_size": min(page_size, 200)}
    data = await client.get("/api/agents/alerts/", params=params)
    return data.get("results", data) if isinstance(data, dict) else data
