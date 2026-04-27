"""
MCP Tools — Announcements
Endpoints: /api/announcements/
"""
from mcp_server import client


async def get_pending_announcements() -> list:
    data = await client.get("/api/announcements/pending/")
    return data.get("results", data) if isinstance(data, dict) else data


async def get_published_announcements(church_id: str = None) -> list:
    params = {}
    if church_id:
        params["church_id"] = church_id
    data = await client.get("/api/announcements/published/", params=params)
    return data.get("results", data) if isinstance(data, dict) else data


async def get_announcement_stats() -> dict:
    return await client.get("/api/announcements/stats/summary/")
