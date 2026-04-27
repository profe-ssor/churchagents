#!/usr/bin/env python3
"""
Smoke-test every orchestrator tool: each name dispatches and returns JSON.

  python scripts/verify_orchestrator_tools.py          # No JWT: RAG path + others return API-unavailable
  python scripts/verify_orchestrator_tools.py --live  # Real JWT + Django (all tools should run without unknown_tool)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env")


def _tool_args_json() -> dict[str, str]:
    """Use AGENT_VERIFY_CHURCH_ID (real Django church UUID) for scoped tools when testing --live."""
    cid = (
        os.getenv("AGENT_VERIFY_CHURCH_ID", "").strip()
        or "00000000-0000-0000-0000-000000000001"
    )
    cid_esc = cid.replace('"', '\\"')
    return {
        "get_church_directory": "{}",
        "get_expiring_subscriptions": "{}",
        "get_failed_payments": "{}",
        "get_payment_history": json.dumps({"church_id": cid}),
        "send_renewal_reminder_email": json.dumps({"church_id": cid, "days_left": 7}),
        "send_sms_alert": json.dumps({"church_id": cid, "message": "Test SMS (smoke)."}),
        "disable_church_access": json.dumps({"church_id": cid}),
        "reinstate_church_access": json.dumps({"church_id": cid}),
        "generate_subscription_report": "{}",
        "notify_support_team": json.dumps({"alert": "Smoke test escalation (orchestrator verify)."}),
        "confirm_outbound_send": json.dumps(
            {"approval_id": "00000000-0000-0000-0000-000000000001"}
        ),
        "send_notification_email": json.dumps(
            {"to": "test@example.com", "subject": "Smoke", "body": "Orchestrator verify."}
        ),
        "send_sms_to_number": json.dumps({"phone_number": "+0000000000", "message": "Smoke SMS verify."}),
        "get_stalled_expense_requests": "{}",
        "get_stalled_programs": "{}",
        "get_upcoming_activities": json.dumps({"church_id": cid, "days": 7}),
        "get_pending_program_approvals": json.dumps({"church_id": cid}),
        "get_department_budget_status": json.dumps({"church_id": cid}),
        "get_department_members": json.dumps(
            {"department_id": "00000000-0000-0000-0000-000000000077"}
        ),
        "get_program_details": json.dumps({"program_id": "00000000-0000-0000-0000-000000000055"}),
        "get_program_approval_history": json.dumps(
            {"program_id": "00000000-0000-0000-0000-000000000055"}
        ),
        "get_activity_detail": json.dumps(
            {
                "department_id": "00000000-0000-0000-0000-000000000077",
                "activity_id": "00000000-0000-0000-0000-000000000066",
            }
        ),
        "notify_department_head": json.dumps(
            {
                "department_id": "00000000-0000-0000-0000-000000000077",
                "message": "Orchestrator verify — dry message (may 404 if department missing).",
            }
        ),
        "send_activity_reminder": json.dumps(
            {
                "department_id": "00000000-0000-0000-0000-000000000077",
                "activity_id": "00000000-0000-0000-0000-000000000066",
            }
        ),
        "get_treasury_statistics": json.dumps({"church_id": cid}),
        "get_income_summary": json.dumps({"church_id": cid, "days": 30}),
        "get_expense_summary": json.dumps({"church_id": cid, "days": 30}),
        "detect_anomalies": json.dumps({"church_id": cid}),
        "get_budget_vs_actual": json.dumps(
            {"church_id": cid, "department_id": "00000000-0000-0000-0000-000000000077"}
        ),
        "get_asset_inventory": json.dumps({"church_id": cid}),
        "generate_financial_report": json.dumps({"church_id": cid, "format": "json"}),
        "send_treasurer_alert": json.dumps(
            {
                "church_id": cid,
                "message": "Smoke test treasurer alert (orchestrator verify only).",
                "to_email": "test@example.com",
            }
        ),
        "get_member_stats": json.dumps({"church_id": cid}),
        "query_member_stats": json.dumps({"church_id": cid}),
        "get_member_profile": json.dumps(
            {"member_id": "00000000-0000-0000-0000-000000000099"}
        ),
        "get_new_members": json.dumps({"church_id": cid, "days": 30}),
        "convert_visitor_to_member": json.dumps(
            {
                "visitor_id": "00000000-0000-0000-0000-000000000088",
                "member_since": "2024-01-01",
                "occupation": "",
                "notes": "orchestrator verify smoke (no-op if visitor missing)",
            }
        ),
        "search_members": json.dumps({"church_id": cid, "query": "a"}),
        "get_church_overview": json.dumps({"church_id": cid}),
        "get_system_status": "{}",
        "generate_daily_briefing": "{}",
        "query_knowledge_base": json.dumps({"question": "test query for RAG"}),
        "list_pending_tasks": "{}",
        "get_audit_logs": json.dumps({"church_id": cid, "range": "week"}),
        "get_failed_login_attempts": json.dumps({"threshold": 5, "church_id": cid}),
        "get_permission_changes": json.dumps({"church_id": cid, "range": "month"}),
        "get_locked_accounts": json.dumps({"church_id": cid}),
        "flag_suspicious_activity": json.dumps(
            {"church_id": cid, "details": "Orchestrator verify — synthetic flag.", "severity": "WARNING"}
        ),
        "generate_audit_report": json.dumps({"church_id": cid, "range": "week"}),
        "send_security_alert": json.dumps(
            {"admin_email": "test@example.com", "message": "Orchestrator security alert smoke test."}
        ),
        "detect_bulk_actions": json.dumps({"church_id": cid, "threshold": 10, "window_minutes": 5}),
        "handoff_to_agent": json.dumps({"agent_name": "treasury", "task": "smoke test"}),
        "gather_specialist_insights": "{}",
        "analytics_members_joined_last_month": json.dumps({"church_id": cid}),
        "analytics_financial_month": json.dumps({"year": 2024, "month": 3, "church_id": cid}),
        "list_trial_plan_churches": "{}",
        "send_birthday_greetings": json.dumps({"church_id": cid}),
    }


def _tool_names() -> list[str]:
    from agents.orchestrator_tools import tool_definitions

    return [t["function"]["name"] for t in tool_definitions() if t.get("type") == "function"]


async def _run(name: str, jwt_ok: bool) -> dict:
    from agents.orchestrator_tools import run_orchestrator_tool

    raw = _tool_args_json().get(name, "{}")
    payload = await run_orchestrator_tool(
        name,
        raw,
        church_hint=None,
        jwt_ok=jwt_ok,
        session_id="orchestrator-tool-verify",
    )
    return json.loads(payload)


async def main_async(live: bool) -> int:
    names = _tool_names()
    ta = _tool_args_json()
    missing = set(ta) - set(names)
    if missing:
        print("Update _tool_args_json() for:", missing)
    failures: list[str] = []

    _TIMEOUT = 45.0

    if live:
        try:
            from mcp_server.auth import get_token

            get_token()
        except Exception as e:
            print("Live mode needs working AGENT_JWT_* and Django:", e)
            return 1
        cid_hint = os.getenv("AGENT_VERIFY_CHURCH_ID", "").strip()
        print("Mode: LIVE (JWT + Django)")
        if cid_hint:
            print(f"Using AGENT_VERIFY_CHURCH_ID={cid_hint[:8]}… for scoped tools.\n")
        else:
            print(
                "Tip: set AGENT_VERIFY_CHURCH_ID to a real church UUID in .env "
                "to avoid 404 on church-scoped calls.\n"
            )
        for n in names:
            try:
                d = await asyncio.wait_for(_run(n, jwt_ok=True), timeout=_TIMEOUT)
            except asyncio.TimeoutError:
                print(f"  [FAIL] {n}  timeout ({_TIMEOUT}s)")
                failures.append(n)
                continue
            except Exception as e:
                print(f"  [FAIL] {n}  exception: {e}")
                failures.append(n)
                continue
            if d.get("error") == "unknown_tool":
                print(f"  [FAIL] {n}  unknown_tool")
                failures.append(n)
            else:
                note = ""
                if isinstance(d.get("error"), str) and d["error"]:
                    note = f" (API: {d['error'][:60]}…)" if len(d["error"]) > 60 else f" (API: {d['error']})"
                print(f"  [PASS] {n}{note}")
    else:
        print("Mode: OFFLINE (no JWT — expect API tools to return django_api_unavailable; RAG may return chunks or Chroma error)\n")
        for n in names:
            try:
                d = await _run(n, jwt_ok=False)
            except Exception as e:
                print(f"  [FAIL] {n}  exception: {e}")
                failures.append(n)
                continue
            if d.get("error") == "unknown_tool":
                print(f"  [FAIL] {n}  unknown_tool")
                failures.append(n)
                continue
            if n == "query_knowledge_base":
                if d.get("error") == "django_api_unavailable":
                    print(f"  [FAIL] {n}  RAG should not be blocked by JWT gate")
                    failures.append(n)
                else:
                    print(f"  [PASS] {n}  (RAG / Chroma path)")
            else:
                if d.get("error") == "django_api_unavailable":
                    print(f"  [PASS] {n}  (expected API gate)")
                else:
                    # still valid if e.g. handoff returns data from import - shouldn't
                    print(f"  [PASS] {n}  (response: {list(d.keys())[:5]})")

    if failures:
        print(f"\nFailed: {failures}")
        return 1
    print(f"\nOK: {len(names)} tool names exercised.")
    return 0


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--live", action="store_true")
    args = p.parse_args()
    raise SystemExit(asyncio.run(main_async(args.live)))


if __name__ == "__main__":
    main()
