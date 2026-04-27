"""
Two-step approval for outbound email/SMS from the orchestrator (human-in-the-loop).

When ORCHESTRATOR_REQUIRE_OUTBOUND_APPROVAL is true (default), send tools called from a
dashboard session must first return a preview + approval_id; the same tool is called again
with outbound_confirmed=true and that approval_id before Django is contacted.

Internal calls with session_id=None bypass the gate (e.g. scheduled jobs).
"""
from __future__ import annotations

import json
import os
import uuid

import redis
from dotenv import load_dotenv

load_dotenv()

_PREFIX = "outbound_approval:"
_TTL_SECONDS = 60 * 60  # 1 hour — avoids expiry during slow human review


def _client() -> redis.Redis:
    return redis.from_url(os.getenv("AGENT_MEMORY_REDIS_URL", "redis://localhost:6379/2"))


def approval_required() -> bool:
    v = os.getenv("ORCHESTRATOR_REQUIRE_OUTBOUND_APPROVAL", "1").strip().lower()
    return v in ("1", "true", "yes", "on")


def _key(session_id: str, approval_id: str) -> str:
    return f"{_PREFIX}{session_id}:{approval_id}"


def create_pending(session_id: str, tool_name: str, payload: dict) -> str:
    """Store payload for later send; returns approval_id."""
    approval_id = str(uuid.uuid4())
    blob = json.dumps({"tool": tool_name, "payload": payload}, default=str)
    _client().setex(_key(session_id, approval_id), _TTL_SECONDS, blob)
    return approval_id


def pop_pending(session_id: str, approval_id: str, expected_tool: str) -> dict | None:
    """Validate tool name, return payload, and delete key."""
    if not session_id or not approval_id:
        return None
    k = _key(session_id, approval_id)
    raw = _client().get(k)
    if not raw:
        return None
    _client().delete(k)
    data = json.loads(raw)
    if data.get("tool") != expected_tool:
        return None
    out = data.get("payload")
    return out if isinstance(out, dict) else None


def pop_pending_any(session_id: str, approval_id: str) -> tuple[str, dict] | None:
    """Pop and return (tool_name, payload) for confirm_outbound_send — any tool."""
    if not session_id or not approval_id:
        return None
    k = _key(session_id, approval_id)
    raw = _client().get(k)
    if not raw:
        return None
    _client().delete(k)
    data = json.loads(raw)
    tool = data.get("tool")
    payload = data.get("payload")
    if not tool or not isinstance(payload, dict):
        return None
    return str(tool), payload
