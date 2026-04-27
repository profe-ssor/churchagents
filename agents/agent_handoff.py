"""
Optional full specialist agent `.run()` — can send emails / create alerts.
Only runs when HANDOFF_EXECUTE_FULL_RUN is truthy in the environment.
"""
from __future__ import annotations

import importlib
import logging
import os
from typing import Any

logger = logging.getLogger("agent_handoff")

_FULL_AGENT_MODULES: dict[str, tuple[str, str]] = {
    "subscription": ("agents.subscription_watchdog", "SubscriptionWatchdogAgent"),
    "subscription_watchdog": ("agents.subscription_watchdog", "SubscriptionWatchdogAgent"),
    "treasury": ("agents.treasury_health", "TreasuryHealthAgent"),
    "treasury_health": ("agents.treasury_health", "TreasuryHealthAgent"),
    "members": ("agents.member_care", "MemberCareAgent"),
    "member_care": ("agents.member_care", "MemberCareAgent"),
    "departments": ("agents.department_program", "DepartmentProgramAgent"),
    "department_program": ("agents.department_program", "DepartmentProgramAgent"),
    "announcements": ("agents.announcement", "AnnouncementAgent"),
    "announcement": ("agents.announcement", "AnnouncementAgent"),
    "audit": ("agents.audit_security", "AuditSecurityAgent"),
    "audit_security": ("agents.audit_security", "AuditSecurityAgent"),
    "secretariat": ("agents.secretariat_agent", "SecretariatAgent"),
}


def _execute_enabled() -> bool:
    return os.getenv("HANDOFF_EXECUTE_FULL_RUN", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


async def run_full_agent_if_enabled(agent_key: str, task_note: str) -> dict[str, Any]:
    """
    Runs the real scheduled agent pipeline (side effects possible).
    """
    if not _execute_enabled():
        return {
            "executed": False,
            "error": "full_run_disabled",
            "hint": (
                "Default handoff returns read-only specialist snapshots only. "
                "Set HANDOFF_EXECUTE_FULL_RUN=true to allow full agent.run() "
                "(may send emails / create alerts)."
            ),
            "task_note": (task_note or "")[:800],
        }

    mod_cls = _FULL_AGENT_MODULES.get(agent_key)
    if not mod_cls:
        return {
            "executed": False,
            "error": "unknown_agent_for_full_run",
            "allowed": sorted(set(_FULL_AGENT_MODULES.keys())),
        }

    mod_name, cls_name = mod_cls
    try:
        mod = importlib.import_module(mod_name)
        cls = getattr(mod, cls_name)
        agent = cls()
        result = await agent.run()
        return {
            "executed": True,
            "agent": agent_key,
            "task_note": (task_note or "")[:800],
            "result": result,
        }
    except Exception as e:
        logger.exception("Full agent run failed: %s", agent_key)
        return {"executed": False, "error": str(e), "agent": agent_key}
