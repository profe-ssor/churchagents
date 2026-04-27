"""
MCP Tools — AuditSecurityAgent (AGENT 7).
Wraps Django /api/activity/ (AuditLog), user lock status, treasury cross-checks, and agent alerts.
"""
from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from mcp_server import client
from mcp_server.tools import agent_infra, notifications, treasury as treasury_tools

AGENT_NAME = "AuditSecurityAgent"


def _unwrap_activity_rows(data: Any) -> list[dict]:
    if isinstance(data, dict):
        rows = data.get("results")
        return rows if isinstance(rows, list) else []
    return data if isinstance(data, list) else []


def _range_to_since_until(range_token: str | None) -> tuple[str | None, str | None]:
    """ISO8601 bounds for API since/until (UTC)."""
    r = (range_token or "week").lower().strip()
    now = datetime.now(timezone.utc)
    if r in ("day", "24h", "today"):
        delta = timedelta(days=1)
    elif r in ("week", "7d"):
        delta = timedelta(days=7)
    elif r in ("month", "30d"):
        delta = timedelta(days=30)
    elif r in ("quarter", "90d"):
        delta = timedelta(days=90)
    else:
        delta = timedelta(days=7)
    since = (now - delta).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    until = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return since, until


async def get_audit_logs(
    church_id: str | None = None,
    action_type: str | None = None,
    range_token: str | None = None,
    page_size: int = 100,
) -> dict[str, Any]:
    """
    Full audit history from Django AuditLog via GET /api/activity/.
    Optional church_id (platform admin), action filter, and time range (day|week|month|quarter).
    """
    params: dict[str, str] = {"page_size": str(min(max(page_size, 1), 100))}
    if church_id:
        params["church_id"] = str(church_id).strip()
    if action_type:
        params["action"] = str(action_type).strip().upper()
    since, until = _range_to_since_until(range_token)
    params["since"] = since
    params["until"] = until
    return await client.get("/api/activity/", params=params)


async def get_failed_login_attempts(threshold: int = 5, church_id: str | None = None) -> dict[str, Any]:
    """Aggregate LOGIN_FAILED rows from the activity feed; groups by user email."""
    params: dict[str, str] = {"action": "LOGIN_FAILED", "page_size": "100"}
    if church_id:
        params["church_id"] = str(church_id).strip()
    since, until = _range_to_since_until("week")
    params["since"] = since
    params["until"] = until
    data = await client.get("/api/activity/", params=params)
    rows = _unwrap_activity_rows(data)
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        key = (row.get("user_email") or row.get("user_display") or "unknown") + "|" + str(
            row.get("ip_address") or ""
        )
        counts[key] += 1
    flagged = {k: v for k, v in counts.items() if v >= threshold}
    return {
        "threshold": threshold,
        "sample_rows": len(rows),
        "aggregates": dict(counts),
        "flagged_brute_force_candidates": flagged,
    }


async def get_permission_changes(
    church_id: str | None = None, range_token: str | None = None
) -> dict[str, Any]:
    """RBAC-related audit rows (PERMISSION_CHANGE, ROLE_CHANGE)."""
    since, until = _range_to_since_until(range_token or "month")
    base: dict[str, str] = {
        "page_size": "100",
        "since": since,
        "until": until,
        "actions": "PERMISSION_CHANGE,ROLE_CHANGE",
    }
    if church_id:
        base["church_id"] = str(church_id).strip()
    data = await client.get("/api/activity/", params=base)
    return {"filter": "PERMISSION_CHANGE,ROLE_CHANGE", "response": data}


async def get_locked_accounts(church_id: str | None = None) -> list[dict[str, Any]]:
    """Users with active time-based lock (failed login policy on User model)."""
    params: dict[str, str] = {"locked_only": "true"}
    if church_id:
        params["church_id"] = str(church_id).strip()
    data = await client.get("/api/auth/users/", params=params)
    return data if isinstance(data, list) else []


async def flag_suspicious_activity(
    church_id: str | None,
    details: str,
    alert_type: str = "SUSPICIOUS_ACTIVITY",
    severity: str = "WARNING",
) -> dict[str, Any]:
    """Create an AgentAlert for the support / security queue (dashboard + logs)."""
    return await agent_infra.create_alert(
        agent_name=AGENT_NAME,
        alert_type=alert_type[:80],
        message=(details or "")[:2000],
        severity=severity if severity in ("INFO", "WARNING", "CRITICAL") else "WARNING",
        church_id=str(church_id).strip() if church_id else None,
    )


async def send_security_alert(admin_email: str, message: str, subject: str | None = None) -> dict[str, Any]:
    """Urgent email to a platform or church admin (Django notifications)."""
    to = (admin_email or "").strip()
    if not to or not (message or "").strip():
        return {"error": "admin_email_and_message_required"}
    subj = (subject or "[Security] Church SaaS alert").strip()[:200]
    return await notifications.send_email(to=to, subject=subj, body=message.strip())


async def detect_bulk_actions(
    church_id: str | None = None,
    threshold: int = 10,
    window_minutes: int = 5,
) -> dict[str, Any]:
    """
    Flag mass DELETE (or UPDATE) in a short window using recent activity rows.
    Uses the narrowest time window supported by fetching recent deletes.
    """
    since_dt = datetime.now(timezone.utc) - timedelta(minutes=max(window_minutes, 1))
    since = since_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    until = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    params: dict[str, str] = {
        "action": "DELETE",
        "page_size": "100",
        "since": since,
        "until": until,
    }
    if church_id:
        params["church_id"] = str(church_id).strip()
    data = await client.get("/api/activity/", params=params)
    rows = _unwrap_activity_rows(data)
    count = len(rows)
    bulk = count >= threshold
    return {
        "window_minutes": window_minutes,
        "threshold": threshold,
        "delete_events_in_window": count,
        "bulk_flag": bulk,
        "sample": rows[:15],
    }


async def generate_audit_report(
    church_id: str | None = None, range_token: str | None = None
) -> dict[str, Any]:
    """
    Structured compliance-style report (JSON). Suitable for export / PDF pipeline later.
    Summarizes auth failures, RBAC changes, deletes, lockouts, optional treasury cross-check.
    """
    since, until = _range_to_since_until(range_token or "month")
    perm = await get_permission_changes(church_id=church_id, range_token=range_token or "month")
    perm_rows = _unwrap_activity_rows(perm.get("response"))
    failed = await get_failed_login_attempts(threshold=5, church_id=church_id)
    locked = await get_locked_accounts(church_id=church_id)
    bulk = await detect_bulk_actions(church_id=church_id, threshold=10, window_minutes=5)
    treasury_note: dict[str, Any] = {}
    if church_id:
        try:
            stats = await treasury_tools.get_treasury_stats(str(church_id).strip())
            large = await treasury_tools.get_large_transactions(
                church_id=str(church_id).strip(), threshold=5000
            )
            treasury_note = {
                "treasury_stats_present": bool(stats and not stats.get("error")),
                "large_transactions_sample_count": len(large) if isinstance(large, list) else 0,
                "cross_reference": (
                    "Elevated treasury activity may warrant review alongside DELETE / "
                    "ROLE_CHANGE events in this period."
                ),
            }
        except Exception as e:
            treasury_note = {"error": str(e)}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "range": range_token or "month",
        "since": since,
        "until": until,
        "church_id": church_id,
        "permission_change_events": len(perm_rows),
        "failed_login_summary": failed,
        "locked_accounts_count": len(locked),
        "locked_accounts_sample": locked[:20],
        "bulk_delete_scan": bulk,
        "treasury": treasury_note,
    }


async def check_unusual_login_hours(
    church_id: str | None = None, odd_hours_utc: tuple[int, ...] = (0, 1, 2, 3, 4, 5, 22, 23)
) -> dict[str, Any]:
    """Heuristic: LOGIN events in off-hours UTC (configurable)."""
    params: dict[str, str] = {"action": "LOGIN", "page_size": "100"}
    if church_id:
        params["church_id"] = str(church_id).strip()
    since, until = _range_to_since_until("week")
    params["since"] = since
    params["until"] = until
    data = await client.get("/api/activity/", params=params)
    rows = _unwrap_activity_rows(data)
    flagged = []
    for row in rows:
        ts = row.get("created_at")
        if not ts:
            continue
        try:
            # ISO from Django
            if isinstance(ts, str):
                hr = datetime.fromisoformat(ts.replace("Z", "+00:00")).hour
            else:
                continue
            if hr in odd_hours_utc:
                flagged.append(
                    {
                        "created_at": ts,
                        "user_email": row.get("user_email"),
                        "ip_address": row.get("ip_address"),
                        "hour_utc": hr,
                    }
                )
        except Exception:
            continue
    return {"odd_hours_utc": odd_hours_utc, "flagged_count": len(flagged), "flagged_sample": flagged[:25]}


def default_platform_admin_email() -> str:
    return (os.getenv("PLATFORM_ADMIN_EMAIL") or "").strip()
