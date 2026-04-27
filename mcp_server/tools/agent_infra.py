"""
MCP Tools — Write back to Django agent models (AgentLog, AgentAlert, AgentTask).
These endpoints will exist once you add agents_app to Django (Day 1 Task 2).
"""
import logging

from guardrails.dry_run import DRY_RUN
from mcp_server import client
from mcp_server.credential_hints import DJANGO_AGENT_AUTH_HELP, looks_like_auth_or_scope_error

logger = logging.getLogger("agent_infra")


async def log_action(
    agent_name: str,
    action: str,
    status: str,
    input_data: dict = None,
    output_data: dict = None,
    error: str = "",
    church_id: str = None,
    triggered_by: str = "SCHEDULED",
    duration_ms: int = 0,
) -> dict:
    """Write a log entry to AgentLog in Django."""
    if DRY_RUN:
        logger.info(f"[DRY RUN] Log: {agent_name} | {action} | {status}")
        return {"status": "dry_run"}
    try:
        return await client.post("/api/agents/logs/", {
            "agent_name": agent_name,
            "action": action,
            "status": status,
            "input_data": input_data or {},
            "output_data": output_data or {},
            "error": error,
            "church_id": church_id,
            "triggered_by": triggered_by,
            "duration_ms": duration_ms,
        })
    except Exception as e:
        logger.error(f"Failed to write agent log: {e}")
        if looks_like_auth_or_scope_error(e):
            logger.error(DJANGO_AGENT_AUTH_HELP)
        return {}


async def create_alert(
    agent_name: str,
    alert_type: str,
    message: str,
    severity: str = "WARNING",
    church_id: str = None,
) -> dict:
    """Create an AgentAlert entry visible in the frontend."""
    if DRY_RUN:
        logger.info(f"[DRY RUN] Alert: {agent_name} | {alert_type} | {severity}")
        return {"status": "dry_run"}
    try:
        return await client.post("/api/agents/alerts/", {
            "agent_name": agent_name,
            "alert_type": alert_type,
            "message": message,
            "severity": severity,
            "church_id": church_id,
        })
    except Exception as e:
        logger.error(f"Failed to create alert: {e}")
        if looks_like_auth_or_scope_error(e):
            logger.error(DJANGO_AGENT_AUTH_HELP)
        return {}
