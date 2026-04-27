"""
MCP Tools — Secretariat (documents, minutes, letters)
Endpoints: /api/secretariat/... (to be added to Django)
"""
from mcp_server import client
from guardrails.dry_run import DRY_RUN
import logging

logger = logging.getLogger("secretariat")


async def get_document_requests(church_id: str = None, status: str = None) -> list:
    params = {}
    if church_id:
        params["church_id"] = church_id
    if status:
        params["status"] = status
    try:
        data = await client.get("/api/secretariat/document-requests/", params=params)
        return data.get("results", data) if isinstance(data, dict) else data
    except Exception as e:
        logger.error(f"get_document_requests failed: {e}")
        return []


async def get_meeting_minutes(church_id: str = None) -> list:
    params = {}
    if church_id:
        params["church_id"] = church_id
    try:
        data = await client.get("/api/secretariat/meeting-minutes/", params=params)
        return data.get("results", data) if isinstance(data, dict) else data
    except Exception as e:
        logger.error(f"get_meeting_minutes failed: {e}")
        return []


async def create_transfer_letter(payload: dict) -> dict:
    """
    payload: {member_id, destination_church, reason, effective_date}
    Returns created letter record.
    """
    if DRY_RUN:
        logger.info(f"[DRY RUN] Transfer letter for member {payload.get('member_id')}")
        return {"status": "dry_run", "payload": payload}
    return await client.post("/api/secretariat/transfer-letters/", payload)


async def create_meeting_minutes(payload: dict) -> dict:
    """
    payload: {title, date, attendees, agenda, decisions, next_meeting_date}
    """
    if DRY_RUN:
        logger.info(f"[DRY RUN] Meeting minutes: {payload.get('title')}")
        return {"status": "dry_run"}
    return await client.post("/api/secretariat/meeting-minutes/", payload)
