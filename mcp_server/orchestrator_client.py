"""
Optional helper: call orchestrator internal /internal/escalate from another agent.

Requires ORCHESTRATOR_INTERNAL_BASE_URL (e.g. http://127.0.0.1:8001) and
ORCHESTRATOR_INTERNAL_SECRET — same secret as orchestrator_server.
"""
from __future__ import annotations

import os
from typing import Any

import httpx


async def escalate_to_orchestrator(
    *,
    from_agent: str,
    urgency: str,
    summary: str,
    church_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = (os.getenv("ORCHESTRATOR_INTERNAL_BASE_URL") or "").rstrip("/")
    secret = (os.getenv("ORCHESTRATOR_INTERNAL_SECRET") or "").strip()
    if not base or not secret:
        return {"skipped": True, "reason": "ORCHESTRATOR_INTERNAL_BASE_URL or SECRET unset"}

    payload = {
        "from_agent": from_agent,
        "urgency": urgency,
        "summary": summary,
        "church_id": church_id,
        "details": details or {},
    }
    url = f"{base}/internal/escalate"
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            url,
            json=payload,
            headers={"X-ChurchAgents-Internal-Key": secret},
        )
        r.raise_for_status()
        return r.json()
