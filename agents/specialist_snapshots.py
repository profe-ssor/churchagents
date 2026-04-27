"""
Read-only specialist domain snapshots for orchestrator handoff (no bulk emails).
Full agent `.run()` is gated separately — see agents/agent_handoff.py.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Awaitable

from mcp_server import client
from mcp_server.tools import accounts, audit_security as audit_snap_tools, departments, treasury
from mcp_server.tools import secretariat as sec_tools
from mcp_server.tools import agent_data

logger = logging.getLogger("specialist_snapshots")

_MAX_CHURCHES_MEMBER_SCAN = 40


async def snapshot_subscription() -> dict[str, Any]:
    expiring = await accounts.get_expiring_subscriptions(days=14)
    trials = await accounts.get_trial_churches()
    suspended = await accounts.get_suspended_churches()
    return {
        "domain": "subscription",
        "expiring_subscriptions_14d_count": len(expiring),
        "trial_or_free_churches_count": len(trials),
        "suspended_or_expired_count": len(suspended),
        "expiring_sample": expiring[:12],
        "trial_sample": [{"id": c.get("id"), "name": c.get("name")} for c in trials[:15]],
    }


async def snapshot_treasury() -> dict[str, Any]:
    """
    Cross-tenant snapshot for orchestrator. Income/expense list endpoints require church scope,
    so large-transaction aggregation without church_id is skipped instead of failing the whole bundle.
    """
    stalled: list = []
    pending: list = []
    large: list = []
    notes: list[str] = []
    try:
        stalled = await treasury.get_stalled_expense_requests()
    except Exception as e:
        notes.append(f"stalled_expense_requests: {e}")
    try:
        pending = await treasury.get_pending_expense_requests()
    except Exception as e:
        notes.append(f"pending_expense_requests: {e}")
    try:
        large = await treasury.get_large_transactions(church_id=None, threshold=5000)
    except Exception as e:
        notes.append(
            f"large_transactions_skipped: {e} "
            "(income/expense APIs need church_id — use get_treasury_statistics per church for detail)"
        )
    out: dict[str, Any] = {
        "domain": "treasury",
        "stalled_expense_requests_count": len(stalled),
        "pending_submitted_expenses_count": len(pending),
        "large_transactions_7d_count": len(large),
        "stalled_sample": stalled[:10],
    }
    if notes:
        out["partial_errors"] = notes
    return out


async def snapshot_members() -> dict[str, Any]:
    churches = await accounts.get_all_churches(page=1, page_size=_MAX_CHURCHES_MEMBER_SCAN)
    if not isinstance(churches, list):
        churches = []
    from mcp_server.tools import members as member_tools

    birthday_by_church: list[dict] = []
    birthday_total = 0
    inactive_hints = 0
    for c in churches[:_MAX_CHURCHES_MEMBER_SCAN]:
        cid = str(c.get("id", ""))
        if not cid:
            continue
        try:
            b = await member_tools.get_birthdays_today(church_id=cid)
            birthday_total += len(b)
            if b:
                birthday_by_church.append(
                    {"church_name": c.get("name"), "birthdays_today": len(b)}
                )
            inc = await member_tools.get_inactive_members(church_id=cid, days=30)
            inactive_hints += len(inc)
        except Exception as e:
            logger.debug("members snapshot slice failed %s: %s", cid, e)

    return {
        "domain": "members",
        "birthdays_today_total_estimated": birthday_total,
        "birthdays_by_church_top": birthday_by_church[:15],
        "inactive_members_30d_rows_sum": inactive_hints,
        "note": f"Scanned up to {_MAX_CHURCHES_MEMBER_SCAN} churches for birthdays/inactive.",
    }


async def snapshot_departments() -> dict[str, Any]:
    stalled = await departments.get_stalled_programs()
    pending = await departments.get_pending_programs()
    return {
        "domain": "departments",
        "stalled_programs_count": len(stalled),
        "pending_submitted_programs_count": len(pending),
        "stalled_sample": stalled[:12],
    }


async def snapshot_announcements() -> dict[str, Any]:
    try:
        data = await client.get("/api/announcements/pending/")
        pending = data.get("results", data) if isinstance(data, dict) else data
        if not isinstance(pending, list):
            pending = []
    except Exception as e:
        return {"domain": "announcements", "error": str(e)}
    return {
        "domain": "announcements",
        "pending_announcements_count": len(pending),
        "pending_sample": pending[:15],
    }


async def snapshot_audit() -> dict[str, Any]:
    try:
        report = await audit_snap_tools.generate_audit_report(church_id=None, range_token="week")
        locked = await audit_snap_tools.get_locked_accounts(church_id=None)
        bulk = await audit_snap_tools.detect_bulk_actions(
            church_id=None, threshold=10, window_minutes=5
        )
    except Exception as e:
        return {"domain": "audit_security", "error": str(e)}
    return {
        "domain": "audit_security",
        "weekly_compliance_summary": report,
        "locked_accounts_count": len(locked) if isinstance(locked, list) else 0,
        "bulk_delete_scan": bulk,
    }


async def snapshot_secretariat() -> dict[str, Any]:
    pending = await sec_tools.get_document_requests(status="PENDING")
    return {
        "domain": "secretariat",
        "pending_document_requests_count": len(pending),
        "pending_sample": pending[:12],
    }


_SNAPSHOTS: dict[str, Callable[[], Awaitable[dict[str, Any]]]] = {
    "subscription": snapshot_subscription,
    "subscription_watchdog": snapshot_subscription,
    "treasury": snapshot_treasury,
    "treasury_health": snapshot_treasury,
    "members": snapshot_members,
    "member_care": snapshot_members,
    "departments": snapshot_departments,
    "department_program": snapshot_departments,
    "announcements": snapshot_announcements,
    "announcement": snapshot_announcements,
    "audit": snapshot_audit,
    "audit_security": snapshot_audit,
    "secretariat": snapshot_secretariat,
}


def normalize_agent_key(name: str) -> str:
    if not name:
        return ""
    k = name.strip().lower().replace(" ", "_").replace("-", "_")
    if k.endswith("_agent"):
        k = k[:-6]
    aliases = {
        "subscriptionwatchdog": "subscription_watchdog",
        "subscriptionwatchdogagent": "subscription_watchdog",
        "treasuryhealth": "treasury_health",
        "treasuryhealthagent": "treasury_health",
        "membercare": "member_care",
        "membercareagent": "member_care",
        "departmentprogram": "department_program",
        "departmentprogramagent": "department_program",
        "announcementagent": "announcements",
        "auditsecurityagent": "audit_security",
        "secretariatagent": "secretariat",
    }
    return aliases.get(k, k)


async def run_specialist_snapshot(agent_name: str, task_note: str = "") -> dict[str, Any]:
    key = normalize_agent_key(agent_name)
    fn = _SNAPSHOTS.get(key)
    if not fn:
        return {
            "error": "unknown_agent",
            "agent": agent_name,
            "allowed": sorted(set(_SNAPSHOTS.keys())),
        }
    out = await fn()
    if task_note:
        out["task_context"] = task_note[:1500]
    return out


_DEFAULT_GATHER = (
    "subscription",
    "treasury",
    "members",
    "departments",
)


async def gather_specialist_insights(agent_keys: list[str] | None = None) -> dict[str, Any]:
    keys = agent_keys or list(_DEFAULT_GATHER)
    tasks = [run_specialist_snapshot(k, "") for k in keys]
    parts = await asyncio.gather(*tasks, return_exceptions=True)
    merged: dict[str, Any] = {"agents": {}}
    for k, p in zip(keys, parts):
        if isinstance(p, Exception):
            merged["agents"][k] = {"error": str(p)}
        else:
            merged["agents"][k] = p
    return merged
