"""
OpenAI function tools for OrchestratorAgent — wraps MCP Django API helpers.

Steps (architecture rollout):
  1) Tool schemas + dispatcher
  2) Platform ops: directory, expiring subscriptions, stalled expenses/programs
  3) Members: stats + search
  4) Aggregated church overview
  5) System status + daily briefing snapshot
"""
from __future__ import annotations

import json
import logging
from difflib import SequenceMatcher
from typing import Any

from mcp_server.tools import accounts, audit_security as audit_tools, departments, members as member_tools, treasury
from mcp_server.tools import agent_data, notifications
from mcp_server.credential_hints import auth_configuration_message, looks_like_auth_or_scope_error

logger = logging.getLogger("orchestrator.tools")

_MAX_JSON_CHARS = 120_000
_TOOLS_WITHOUT_JWT = frozenset({"query_knowledge_base"})


def _gate_outbound(
    session_id: str | None,
    tool_name: str,
    args: dict,
    payload: dict,
    channel: str,
) -> tuple[str | None, dict]:
    """
    Human-in-the-loop gate for outbound messages (when ORCHESTRATOR_REQUIRE_OUTBOUND_APPROVAL=1).
    Returns (early_json_response_or_None, payload_to_use). Empty dict as second value means abort.
    """
    from agents.outbound_approval import approval_required, create_pending, pop_pending

    sid = (session_id or "").strip()
    if not approval_required() or not sid:
        return None, payload

    if bool(args.get("outbound_confirmed")):
        aid = (args.get("approval_id") or "").strip()
        if not aid:
            return (
                _json_payload({"error": "approval_id_required_when_outbound_confirmed_is_true"}),
                {},
            )
        stored = pop_pending(sid, aid, tool_name)
        if stored is None:
            return _json_payload({"error": "invalid_or_expired_approval_id"}), {}
        return None, stored

    approval_id = create_pending(sid, tool_name, dict(payload))
    return (
        _json_payload(
            {
                "needs_approval": True,
                "approval_id": approval_id,
                "channel": channel,
                "preview": payload,
                "instruction": (
                    "Show this preview to the administrator. When they approve, call confirm_outbound_send "
                    "with ONLY approval_id copied from above (preferred). Alternatively re-call this tool "
                    "with outbound_confirmed=true and the same approval_id."
                ),
            }
        ),
        {},
    )


def _json_payload(data: Any) -> str:
    s = json.dumps(data, default=str)
    if len(s) > _MAX_JSON_CHARS:
        return s[: _MAX_JSON_CHARS] + "\n… (truncated)"
    return s


def tool_definitions() -> list[dict[str, Any]]:
    """OpenAI Chat Completions `tools` list."""
    return [
        {
            "type": "function",
            "function": {
                "name": "get_church_directory",
                "description": (
                    "List churches/tenants visible to the API token (platform admin sees all). "
                    "Use for questions about all churches, tenant lists, or org counts."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "page_size": {
                            "type": "integer",
                            "description": "Maximum churches to return (default 500).",
                        }
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "confirm_outbound_send",
                "description": (
                    "**Use this after the human approves a preview.** Pass only the approval_id UUID "
                    "from the prior needs_approval tool response. Required to actually send email/SMS — "
                    "chat text like \"yes\" or \"I approve\" does not send anything without this tool call."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "approval_id": {
                            "type": "string",
                            "description": "Exact approval_id string from needs_approval JSON.",
                        },
                    },
                    "required": ["approval_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_expiring_subscriptions",
                "description": (
                    "Churches whose ACTIVE subscription expires within N days. "
                    "Use for renewal risk and trial/expiry questions."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {
                            "type": "integer",
                            "description": "Horizon in days (default 7).",
                        },
                        "days_ahead": {
                            "type": "integer",
                            "description": "Same as days; use either (default 7).",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_failed_payments",
                "description": "List recent Paystack/Django Payment rows with status FAILED.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "page_size": {
                            "type": "integer",
                            "description": "Max rows (default 100, max 500).",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_payment_history",
                "description": "Payment log for one church (amounts, references, SUCCESS/FAILED/PENDING).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {"type": "string", "description": "Church UUID."},
                        "page_size": {
                            "type": "integer",
                            "description": "Max rows (default 100).",
                        },
                    },
                    "required": ["church_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "send_renewal_reminder_email",
                "description": "Send templated subscription expiry reminder email to the church admin.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {"type": "string"},
                        "days_left": {"type": "integer"},
                        "outbound_confirmed": {
                            "type": "boolean",
                            "description": "True only after the admin approved the preview (if approval is on).",
                        },
                        "approval_id": {
                            "type": "string",
                            "description": "From needs_approval; use with outbound_confirmed.",
                        },
                    },
                    "required": ["church_id", "days_left"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "send_sms_alert",
                "description": "SMS the church primary phone via Django notifications (Twilio/backend).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {"type": "string"},
                        "message": {"type": "string"},
                        "outbound_confirmed": {
                            "type": "boolean",
                            "description": "True only after the admin approved the preview (if approval is on).",
                        },
                        "approval_id": {"type": "string"},
                    },
                    "required": ["church_id", "message"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "disable_church_access",
                "description": "Disable tenant login/API (subscription enforcement). Platform scope.",
                "parameters": {
                    "type": "object",
                    "properties": {"church_id": {"type": "string"}},
                    "required": ["church_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "reinstate_church_access",
                "description": "Re-enable tenant access after payment confirmed.",
                "parameters": {
                    "type": "object",
                    "properties": {"church_id": {"type": "string"}},
                    "required": ["church_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "generate_subscription_report",
                "description": (
                    "Platform-wide snapshot: tenant counts, expiring subs, trial/suspended counts, "
                    "failed/pending Paystack-linked payments."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "notify_support_team",
                "description": (
                    "Escalate to SUPPORT_TEAM_EMAIL (if set) and create CRITICAL AgentAlert."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "alert": {"type": "string", "description": "Human-readable escalation text."},
                        "outbound_confirmed": {
                            "type": "boolean",
                            "description": "True only after the admin approved the preview (if approval is on).",
                        },
                        "approval_id": {"type": "string"},
                    },
                    "required": ["alert"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_stalled_expense_requests",
                "description": (
                    "Expense requests stuck in SUBMITTED state longer than a threshold. "
                    "Optional church_id scopes to one church."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {
                            "type": "string",
                            "description": "UUID of the church to scope stalled requests.",
                        },
                        "hours": {
                            "type": "integer",
                            "description": "Hours pending before considered stalled (default 48).",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_stalled_programs",
                "description": (
                    "Department programs pending approval longer than a threshold. "
                    "Optionally filter to one church_id."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {
                            "type": "string",
                            "description": "UUID of the church to filter stalled programs.",
                        },
                        "hours": {
                            "type": "integer",
                            "description": "Hours pending before considered stalled (default 72).",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_upcoming_activities",
                "description": (
                    "Department activities in the next N days for one church (aggregated across departments). "
                    "Requires church scope (church_id, church_name, or dashboard session)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {"type": "string"},
                        "church_name": {
                            "type": "string",
                            "description": "Resolve tenant when UUID unknown (substring match against directory).",
                        },
                        "days": {
                            "type": "integer",
                            "description": "Lookahead window in days (default 7, max 365).",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_pending_program_approvals",
                "description": (
                    "Programs still in workflow before final approval "
                    "(SUBMITTED through treasury-approved states). Scoped to one church."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {"type": "string"},
                        "church_name": {"type": "string"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_department_budget_status",
                "description": (
                    "Per-department program budget utilization / pressure signals for one church "
                    "(delegates to treasury scan). Requires church scope."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {"type": "string"},
                        "church_name": {"type": "string"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_department_members",
                "description": "Members assigned to a department (MemberDepartment rows).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "department_id": {"type": "string", "description": "Department UUID."},
                    },
                    "required": ["department_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_program_details",
                "description": "Full program record by UUID (budget lines when exposed by API).",
                "parameters": {
                    "type": "object",
                    "properties": {"program_id": {"type": "string"}},
                    "required": ["program_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_program_approval_history",
                "description": (
                    "Synthetic approval timeline from program timestamp fields (best-effort; no separate audit API)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"program_id": {"type": "string"}},
                    "required": ["program_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_activity_detail",
                "description": (
                    "Single department activity by department_id and activity_id (nested route). "
                    "Both IDs are required."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "department_id": {"type": "string"},
                        "activity_id": {"type": "string"},
                    },
                    "required": ["department_id", "activity_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "notify_department_head",
                "description": (
                    "Email the primary department head (resolved from department heads + member profile). "
                    "Subject to outbound approval when enabled."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "department_id": {"type": "string"},
                        "message": {"type": "string"},
                        "subject": {
                            "type": "string",
                            "description": "Optional; defaults to a department notice subject.",
                        },
                        "church_id": {
                            "type": "string",
                            "description": "Optional tenant id for notification linkage.",
                        },
                        "church_name": {"type": "string"},
                        "outbound_confirmed": {"type": "boolean"},
                        "approval_id": {"type": "string"},
                    },
                    "required": ["department_id", "message"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "send_activity_reminder",
                "description": (
                    "Email the department head with a structured reminder for one activity. "
                    "Requires both department_id and activity_id. Optional extra_message appended to the body. "
                    "Uses outbound approval when enabled."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "department_id": {"type": "string"},
                        "activity_id": {"type": "string"},
                        "extra_message": {"type": "string"},
                        "church_id": {"type": "string"},
                        "church_name": {"type": "string"},
                        "outbound_confirmed": {"type": "boolean"},
                        "approval_id": {"type": "string"},
                    },
                    "required": ["department_id", "activity_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_treasury_statistics",
                "description": (
                    "KPI-style snapshot from GET /api/treasury/statistics/ (totals, income vs expenses) for one church. "
                    "Same data as the dashboard financial snapshot."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {"type": "string"},
                        "church_name": {
                            "type": "string",
                            "description": "Resolve church by name when UUID unknown.",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_income_summary",
                "description": (
                    "Income totals by category for a date range (from income transaction lines; client-aggregated)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {"type": "string"},
                        "church_name": {"type": "string"},
                        "start_date": {
                            "type": "string",
                            "description": "YYYY-MM-DD inclusive (optional if using days back).",
                        },
                        "end_date": {"type": "string", "description": "YYYY-MM-DD inclusive."},
                        "days": {
                            "type": "integer",
                            "description": "If start/end omitted, last N days ending today (default 30).",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_expense_summary",
                "description": (
                    "Expense breakdown by category and by department name for a date range (client-aggregated)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {"type": "string"},
                        "church_name": {"type": "string"},
                        "start_date": {"type": "string"},
                        "end_date": {"type": "string"},
                        "days": {"type": "integer"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "detect_anomalies",
                "description": (
                    "Flag income and expense transactions at or above the anomaly amount threshold "
                    "(default ANOMALY_TRANSACTION_THRESHOLD) within the last few days."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {"type": "string"},
                        "church_name": {"type": "string"},
                        "threshold": {"type": "number", "description": "Minimum amount to flag."},
                        "days": {"type": "integer", "description": "Lookback window (default 7)."},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_budget_vs_actual",
                "description": (
                    "Budget utilization signals for one department: compares program budget totals "
                    "(income/expense lines on programs) to summed expense transactions tagged with that department."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {"type": "string"},
                        "church_name": {"type": "string"},
                        "department_id": {"type": "string", "description": "Department UUID."},
                    },
                    "required": ["department_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_asset_inventory",
                "description": (
                    "List tangible assets from treasury (tags, categories, values). Requires church-scoped API access."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {"type": "string"},
                        "church_name": {"type": "string"},
                        "page_size": {"type": "integer"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "generate_financial_report",
                "description": (
                    "Build a structured JSON financial bundle (statistics, stalled expenses, anomalies, monthly slice). "
                    "Does not produce binary PDF/XLSX; use format pdf/xlsx only to receive a polite note."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {"type": "string"},
                        "church_name": {"type": "string"},
                        "format": {
                            "type": "string",
                            "description": 'Usually "json"; pdf/xlsx/csv return guidance only.',
                        },
                        "year": {"type": "integer"},
                        "month": {"type": "integer", "description": "Include calendar month totals when both set."},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "send_treasurer_alert",
                "description": (
                    "Email the church treasurer / primary church email with a treasury message "
                    "(optional explicit to_email override). Uses outbound approval when enabled."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {"type": "string"},
                        "church_name": {"type": "string"},
                        "message": {"type": "string"},
                        "subject": {"type": "string"},
                        "to_email": {"type": "string", "description": "Override recipient if not the church email."},
                        "outbound_confirmed": {"type": "boolean"},
                        "approval_id": {"type": "string"},
                    },
                    "required": ["message"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_member_stats",
                "description": (
                    "Member counts (active/inactive/visitor) for one church — same as query_member_stats. "
                    "Provide church_id (UUID) OR church_name (substring matched against directory), "
                    "or rely on session church context when available."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {"type": "string", "description": "Church UUID when known."},
                        "church_name": {
                            "type": "string",
                            "description": (
                                "Human-readable church name or substring (e.g. \"Adenta Central\") "
                                "when UUID is unknown; resolved via directory."
                            ),
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_members",
                "description": (
                    "Find members in a church by substring match on name or email. "
                    "Needs church scope: church_id OR church_name (directory match) or session church."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {"type": "string"},
                        "church_name": {"type": "string", "description": "Church display name substring if UUID unknown."},
                        "query": {
                            "type": "string",
                            "description": "Substring to match (case-insensitive). Empty returns first page summary only.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max rows to return after filtering (default 40).",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_member_stats",
                "description": (
                    "Aggregate membership stats for one church (alias of get_member_stats — active/inactive/visitor counts)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {"type": "string"},
                        "church_name": {"type": "string"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_member_profile",
                "description": "Fetch full profile for one member UUID (MemberCare lifecycle tooling).",
                "parameters": {
                    "type": "object",
                    "properties": {"member_id": {"type": "string"}},
                    "required": ["member_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_new_members",
                "description": (
                    "Members whose join date falls within the last N days for a church (lifecycle / welcome workflows)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {"type": "string"},
                        "church_name": {"type": "string"},
                        "days": {
                            "type": "integer",
                            "description": "Look-back window in days (default 7).",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "convert_visitor_to_member",
                "description": (
                    "Convert an existing visitor record to a church member via Django POST "
                    "visitors/convert-to-member (member_since date required)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "visitor_id": {"type": "string"},
                        "member_since": {
                            "type": "string",
                            "description": "YYYY-MM-DD membership start date.",
                        },
                        "occupation": {"type": "string"},
                        "notes": {"type": "string"},
                    },
                    "required": ["visitor_id", "member_since"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_church_overview",
                "description": (
                    "Aggregated snapshot for one church: profile, member stats, treasury stats, "
                    "department/program counts, stalled items. Use church_id OR church_name "
                    "(name substring matched via directory)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {"type": "string", "description": "Church UUID."},
                        "church_name": {
                            "type": "string",
                            "description": "Display name substring when the user names a church but not its UUID.",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_system_status",
                "description": (
                    "Platform-wide health snapshot: tenant count, expiring subscriptions, "
                    "stalled expenses/programs totals. No church scope required."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "generate_daily_briefing",
                "description": (
                    "Build a structured briefing for admins: platform system status plus optional "
                    "church drill-down. Pass church_id OR church_name (e.g. \"Adenta Central\") "
                    "when the user asks for a specific church."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {
                            "type": "string",
                            "description": "Church UUID for church-level drill-down.",
                        },
                        "church_name": {
                            "type": "string",
                            "description": (
                                "Church name or distinctive substring — matched against directory "
                                "when UUID is unknown."
                            ),
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "query_knowledge_base",
                "description": (
                    "RAG retrieval from the indexed church knowledge base (ChromaDB). "
                    "Use together with API tools — KB may be empty until documents are ingested."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string", "description": "Natural-language query."},
                        "n_results": {"type": "integer", "description": "Chunks to return (default 8)."},
                        "church_id": {
                            "type": "string",
                            "description": "Optional tenant filter when metadata uses church_id.",
                        },
                    },
                    "required": ["question"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_pending_tasks",
                "description": (
                    "Unified backlog: agent alerts, stalled approvals, pending expenses/programs, "
                    "soon-expiring subscriptions, trial tenants. Answers 'what needs attention now'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {"type": "string", "description": "Optional scope UUID."},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_audit_logs",
                "description": (
                    "AuditSecurityAgent: paginated audit trail from GET /api/activity/ "
                    "(logins, deletes, RBAC). Optional church_id, action_type, range (day|week|month|quarter)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {"type": "string"},
                        "action_type": {"type": "string"},
                        "range": {
                            "type": "string",
                            "description": "day | week | month | quarter (default week)",
                        },
                        "page_size": {"type": "integer"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_failed_login_attempts",
                "description": (
                    "AuditSecurityAgent: aggregate LOGIN_FAILED events from the activity feed; "
                    "flags keys meeting threshold (brute-force style)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "threshold": {"type": "integer", "description": "Default 5."},
                        "church_id": {"type": "string"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_permission_changes",
                "description": (
                    "AuditSecurityAgent: PERMISSION_CHANGE and ROLE_CHANGE audit rows for a period."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {"type": "string"},
                        "range": {"type": "string", "description": "day | week | month | quarter"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_locked_accounts",
                "description": (
                    "AuditSecurityAgent: users with active account_locked_until (failed-login lockout)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"church_id": {"type": "string"}},
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "flag_suspicious_activity",
                "description": (
                    "AuditSecurityAgent: create AgentAlert for support (optionally scoped to church_id)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {"type": "string"},
                        "details": {"type": "string"},
                        "alert_type": {"type": "string"},
                        "severity": {"type": "string", "description": "INFO | WARNING | CRITICAL"},
                    },
                    "required": ["details"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "generate_audit_report",
                "description": (
                    "AuditSecurityAgent: structured compliance-style JSON report for a range "
                    "(auth failures, RBAC, lockouts, bulk deletes, optional treasury cross-check when church_id set). "
                    "Not a binary PDF — export-friendly JSON."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {"type": "string"},
                        "range": {"type": "string"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "send_security_alert",
                "description": (
                    "AuditSecurityAgent: urgent email to platform or church admin via Django notifications."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "admin_email": {"type": "string"},
                        "message": {"type": "string"},
                        "subject": {"type": "string"},
                        "outbound_confirmed": {"type": "boolean"},
                        "approval_id": {"type": "string"},
                    },
                    "required": ["admin_email", "message"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "detect_bulk_actions",
                "description": (
                    "AuditSecurityAgent: count DELETE audit events in a short window vs threshold (mass delete signal)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {"type": "string"},
                        "threshold": {"type": "integer", "description": "Default 10."},
                        "window_minutes": {"type": "integer", "description": "Default 5."},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "handoff_to_agent",
                "description": (
                    "Delegate to a specialist domain. DEFAULT: returns a read-only snapshot "
                    "(no bulk emails). Set execute_full_run=true ONLY if HANDOFF_EXECUTE_FULL_RUN "
                    "is enabled in env — runs the full scheduled agent including emails/alerts."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "agent_name": {
                            "type": "string",
                            "description": (
                                "subscription | treasury | members | departments | announcements | "
                                "audit | secretariat (suffixes like _watchdog OK)"
                            ),
                        },
                        "task": {"type": "string", "description": "Short task description / context."},
                        "execute_full_run": {
                            "type": "boolean",
                            "description": "If true, runs full agent pipeline (dangerous — gated by env).",
                        },
                    },
                    "required": ["agent_name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "gather_specialist_insights",
                "description": (
                    "Runs multiple read-only specialist snapshots in parallel for cross-domain synthesis "
                    "(default bundle: subscription, treasury, members, departments)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "agent_names": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional list of specialist keys; omit for default bundle.",
                        }
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "analytics_members_joined_last_month",
                "description": "Count members who joined during the previous calendar month for one church.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {"type": "string"},
                        "church_name": {"type": "string"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "analytics_financial_month",
                "description": (
                    "Total income and expenses for a calendar month (from paginated transaction lists)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "year": {"type": "integer"},
                        "month": {"type": "integer", "description": "1–12"},
                        "church_id": {"type": "string"},
                        "church_name": {"type": "string"},
                    },
                    "required": ["year", "month"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_trial_plan_churches",
                "description": "Churches on TRIAL or FREE subscription plans.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "send_birthday_greetings",
                "description": (
                    "Members with birthdays today for a church. "
                    "If outbound approval is on, first call returns a preview; then use "
                    "outbound_confirmed+approval_id, then confirm_send=true and "
                    "BIRTHDAY_GREETINGS_ALLOW_SEND=true to actually send."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "church_id": {"type": "string"},
                        "church_name": {"type": "string"},
                        "outbound_confirmed": {
                            "type": "boolean",
                            "description": "True only after the admin approved the preview (if approval is on).",
                        },
                        "approval_id": {"type": "string"},
                        "confirm_send": {
                            "type": "boolean",
                            "description": "Must be true to attempt sending birthday emails (after approval if required).",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "send_notification_email",
                "description": (
                    "Send a single email through the church platform (Django notifications). "
                    "Use for welcome messages, one-off admin notices, or tests when the user gives "
                    "recipient, subject, and body. Optional church_id for audit/tenant scoping."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "string",
                            "description": "Recipient email address.",
                        },
                        "subject": {"type": "string"},
                        "body": {"type": "string"},
                        "church_id": {
                            "type": "string",
                            "description": "Optional church UUID for notification linkage.",
                        },
                        "outbound_confirmed": {
                            "type": "boolean",
                            "description": "True only after the admin approved the preview (if approval is on).",
                        },
                        "approval_id": {"type": "string"},
                    },
                    "required": ["to", "subject", "body"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "send_sms_to_number",
                "description": (
                    "Send one SMS via Django (Twilio/configured backend). Use when the user gives "
                    "a phone number and message. Optional church_id for tenant scope (defaults from "
                    "dashboard session when omitted)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "phone_number": {
                            "type": "string",
                            "description": "E.164 or format your Django SMS endpoint accepts.",
                        },
                        "message": {"type": "string"},
                        "church_id": {
                            "type": "string",
                            "description": "Optional church UUID; required for platform admins unless AGENT_JWT_CHURCH_ID is set.",
                        },
                        "outbound_confirmed": {
                            "type": "boolean",
                            "description": "True only after the admin approved the preview (if approval is on).",
                        },
                        "approval_id": {"type": "string"},
                    },
                    "required": ["phone_number", "message"],
                },
            },
        },
    ]


def _resolve_church_id(args: dict, church_hint: str | None) -> str | None:
    raw = (args.get("church_id") or "").strip()
    if raw:
        return raw
    return (church_hint or "").strip() or None


async def _resolve_church_for_scope(
    args: dict,
    church_hint: str | None,
) -> tuple[str | None, dict[str, Any]]:
    """
    Resolve a church UUID from explicit church_id, session hint, or church_name
    (case-insensitive substring match against get_all_churches).
    """
    cid = _resolve_church_id(args, church_hint)
    if cid:
        return cid, {"resolved_from": "uuid_or_session"}

    name_q = (args.get("church_name") or "").strip()
    if not name_q:
        return None, {}

    churches = await accounts.get_all_churches(page=1, page_size=500)
    if not isinstance(churches, list):
        churches = []
    needle = name_q.lower()
    matches: list[dict] = []
    for c in churches:
        if not isinstance(c, dict):
            continue
        n = (c.get("name") or "").strip()
        if needle in n.lower():
            matches.append(c)

    if len(matches) == 1:
        return str(matches[0].get("id")), {
            "resolved_from": "church_name",
            "matched_name": matches[0].get("name"),
        }
    if len(matches) > 1:
        return None, {
            "church_name_resolution": "ambiguous",
            "church_name_query": name_q,
            "candidates": [
                {"id": str(c.get("id")), "name": c.get("name")} for c in matches[:30]
            ],
        }

    # Fuzzy whole-string match for typos (e.g. "Adneta" vs "Adenta Central SDA")
    best_c: dict | None = None
    best_score = 0.0
    for c in churches:
        if not isinstance(c, dict):
            continue
        cn = (c.get("name") or "").strip()
        if not cn:
            continue
        score = SequenceMatcher(None, needle, cn.lower()).ratio()
        if score > best_score:
            best_score = score
            best_c = c
    thresh = 0.86 if len(needle) < 10 else 0.78
    if best_c is not None and best_score >= thresh:
        return str(best_c.get("id")), {
            "resolved_from": "church_name_fuzzy",
            "matched_name": best_c.get("name"),
            "similarity": round(best_score, 3),
            "church_name_query": name_q,
        }

    return None, {
        "church_name_resolution": "no_match",
        "church_name_query": name_q,
        "hint": "Try get_church_directory or a shorter/longer substring of the church name.",
    }


async def _dispatch_confirmed_outbound(inner_tool: str, p: dict[str, Any]) -> str:
    """Execute stored payload after confirm_outbound_send (must match gated tools)."""
    try:
        if inner_tool == "send_notification_email":
            result = await notifications.send_email(
                to=str(p["to"]),
                subject=str(p["subject"]),
                body=str(p["body"]),
                church_id=p.get("church_id"),
            )
            return _json_payload(
                {"status": "ok", "django_response": result, "via": "confirm_outbound_send"}
            )
        if inner_tool == "send_sms_to_number":
            result = await notifications.send_sms(
                to_phone=str(p["phone_number"]),
                message=str(p["message"]),
                church_id=p.get("church_id"),
            )
            return _json_payload(
                {"status": "ok", "django_response": result, "via": "confirm_outbound_send"}
            )
        if inner_tool == "send_renewal_reminder_email":
            result = await accounts.send_renewal_reminder_email(
                str(p["church_id"]), int(p["days_left"])
            )
            out_rm = dict(result) if isinstance(result, dict) else {"result": result}
            out_rm["via"] = "confirm_outbound_send"
            return _json_payload(out_rm)
        if inner_tool == "send_sms_alert":
            result = await accounts.send_sms_alert(str(p["church_id"]), str(p["message"]))
            out_sa = dict(result) if isinstance(result, dict) else {"result": result}
            out_sa["via"] = "confirm_outbound_send"
            return _json_payload(out_sa)
        if inner_tool == "notify_support_team":
            result = await accounts.notify_support_team(str(p["alert"]))
            out_nt = dict(result) if isinstance(result, dict) else {"result": result}
            out_nt["via"] = "confirm_outbound_send"
            return _json_payload(out_nt)
        if inner_tool == "security_alert_email":
            result = await audit_tools.send_security_alert(
                admin_email=str(p["admin_email"]),
                message=str(p["message"]),
                subject=str(p["subject"]) if p.get("subject") else None,
            )
            out_sec = dict(result) if isinstance(result, dict) else {"result": result}
            out_sec["via"] = "confirm_outbound_send"
            return _json_payload(out_sec)
        if inner_tool == "send_birthday_greetings":
            import os as _os

            cid = str(p["church_id"])
            allow_env = _os.getenv("BIRTHDAY_GREETINGS_ALLOW_SEND", "").lower() in (
                "1",
                "true",
                "yes",
            )
            if not allow_env:
                return _json_payload(
                    {
                        "error": "birthday_send_disabled",
                        "detail": "Set BIRTHDAY_GREETINGS_ALLOW_SEND=true to send after approval.",
                    }
                )
            bday = await member_tools.get_birthdays_today(church_id=cid)
            church = await accounts.get_church(cid)
            cname = (church.get("name") if isinstance(church, dict) else None) or "your church"
            sent: list[str] = []
            errors: list[dict[str, Any]] = []
            for m in bday if isinstance(bday, list) else []:
                to = (m.get("email") or "").strip()
                if not to:
                    errors.append({"member_id": m.get("id"), "error": "no_email"})
                    continue
                fn = m.get("first_name") or "Friend"
                try:
                    await notifications.send_email(
                        to=to,
                        subject=f"Happy Birthday, {fn}! — {cname}",
                        body=(
                            f"Warm birthday greetings from everyone at {cname}!\n\n"
                            f"We're grateful for you and pray for a blessed year ahead."
                        ),
                        church_id=cid,
                    )
                    sent.append(to)
                except Exception as e:
                    errors.append({"email": to, "error": str(e)})
            return _json_payload(
                {
                    "dry_run": False,
                    "sent_count": len(sent),
                    "sent_to": sent,
                    "errors": errors,
                    "via": "confirm_outbound_send",
                }
            )
        if inner_tool == "notify_department_head":
            subj_raw = str(p.get("subject") or "").strip()
            r = await departments.notify_department_head(
                str(p["department_id"]),
                str(p["body"]),
                subject=subj_raw if subj_raw else None,
                church_id=p.get("church_id"),
            )
            out_ndh = dict(r) if isinstance(r, dict) else {"result": r}
            out_ndh["via"] = "confirm_outbound_send"
            return _json_payload(out_ndh)
        if inner_tool == "send_activity_reminder":
            extra = p.get("extra_message")
            if isinstance(extra, str) and not extra.strip():
                extra = None
            r = await departments.send_activity_reminder(
                str(p["department_id"]),
                str(p["activity_id"]),
                church_id=p.get("church_id"),
                extra_message=extra if isinstance(extra, str) else None,
            )
            out_sar = dict(r) if isinstance(r, dict) else {"result": r}
            out_sar["via"] = "confirm_outbound_send"
            return _json_payload(out_sar)
    except KeyError as e:
        return _json_payload({"error": "pending_payload_missing_field", "field": str(e)})
    except Exception as e:
        logger.warning("confirm dispatch failed: %s", e)
        err: dict[str, Any] = {"error": str(e), "via": "confirm_outbound_send"}
        if looks_like_auth_or_scope_error(e):
            err["configuration_help"] = auth_configuration_message()
        return _json_payload(err)

    return _json_payload({"error": "unknown_pending_tool", "tool": inner_tool})


async def run_orchestrator_tool(
    tool_name: str,
    raw_arguments: str | None,
    *,
    church_hint: str | None,
    jwt_ok: bool,
    session_id: str | None = None,
) -> str:
    """Execute one tool; return JSON string for the assistant message."""
    if not jwt_ok and tool_name not in _TOOLS_WITHOUT_JWT:
        return _json_payload(
            {
                "error": "django_api_unavailable",
                "detail": "Configure AGENT_JWT_EMAIL and AGENT_JWT_PASSWORD for live data.",
            }
        )

    try:
        args = json.loads(raw_arguments or "{}")
    except json.JSONDecodeError:
        args = {}

    try:
        if tool_name == "confirm_outbound_send":
            from agents.outbound_approval import pop_pending_any

            sid = (session_id or "").strip()
            if not sid:
                return _json_payload(
                    {
                        "error": "session_required",
                        "detail": "Use the same chat session as the preview so approval_id matches Redis.",
                    }
                )
            aid = (args.get("approval_id") or "").strip()
            if not aid:
                return _json_payload({"error": "approval_id_required"})
            popped = pop_pending_any(sid, aid)
            if popped is None:
                return _json_payload(
                    {
                        "error": "invalid_or_expired_approval_id",
                        "hint": (
                            "Run the send tool again for a fresh preview, then call confirm_outbound_send "
                            "with the new approval_id immediately after the user approves."
                        ),
                    }
                )
            inner_t, payload = popped
            return await _dispatch_confirmed_outbound(inner_t, payload)

        if tool_name == "get_church_directory":
            page_size = int(args.get("page_size") or 500)
            churches = await accounts.get_all_churches(page=1, page_size=min(page_size, 500))
            if not isinstance(churches, list):
                churches = []
            rows = []
            for c in churches[:500]:
                if not isinstance(c, dict):
                    continue
                rows.append(
                    {
                        "id": c.get("id"),
                        "name": c.get("name"),
                        "subscription_status": c.get("subscription_status") or c.get("status"),
                    }
                )
            return _json_payload({"total": len(churches), "churches": rows})

        if tool_name == "get_expiring_subscriptions":
            raw_days = args.get("days_ahead")
            if raw_days is None:
                raw_days = args.get("days")
            days = int(raw_days if raw_days is not None else 7)
            expiring = await accounts.get_expiring_subscriptions(days_ahead=days)
            slim = [
                {
                    "id": c.get("id"),
                    "name": c.get("name"),
                    "days_remaining": c.get("days_remaining"),
                    "subscription_expiry": c.get("subscription_expiry")
                    or c.get("subscription_end_date"),
                }
                for c in expiring
            ]
            return _json_payload({"days": days, "count": len(slim), "expiring": slim})

        if tool_name == "get_failed_payments":
            ps = min(int(args.get("page_size") or 100), 500)
            rows = await accounts.get_failed_payments(page_size=ps)
            return _json_payload({"count": len(rows), "failed_payments": rows[:200]})

        if tool_name == "get_payment_history":
            cid = (args.get("church_id") or "").strip()
            if not cid:
                return _json_payload({"error": "church_id_required"})
            ps = min(int(args.get("page_size") or 100), 500)
            rows = await accounts.get_payment_history(church_id=cid, page_size=ps)
            return _json_payload(
                {"church_id": cid, "count": len(rows), "payments": rows[:200]}
            )

        if tool_name == "send_renewal_reminder_email":
            cid = (args.get("church_id") or "").strip()
            dl = int(args.get("days_left") or 0)
            if not cid or dl < 1:
                return _json_payload({"error": "church_id_and_positive_days_left_required"})
            payload_rm = {"church_id": cid, "days_left": dl}
            early, resolved = _gate_outbound(
                session_id,
                tool_name,
                args,
                payload_rm,
                "renewal_reminder_email",
            )
            if early:
                return early
            cid = str(resolved["church_id"])
            dl = int(resolved["days_left"])
            result = await accounts.send_renewal_reminder_email(cid, dl)
            return _json_payload(result)

        if tool_name == "send_sms_alert":
            cid = (args.get("church_id") or "").strip()
            msg = (args.get("message") or "").strip()
            if not cid or not msg:
                return _json_payload({"error": "church_id_and_message_required"})
            payload_sa = {"church_id": cid, "message": msg}
            early, resolved = _gate_outbound(
                session_id,
                tool_name,
                args,
                payload_sa,
                "sms_to_church_phone",
            )
            if early:
                return early
            cid = str(resolved["church_id"])
            msg = str(resolved["message"])
            result = await accounts.send_sms_alert(cid, msg)
            return _json_payload(result)

        if tool_name == "disable_church_access":
            cid = (args.get("church_id") or "").strip()
            if not cid:
                return _json_payload({"error": "church_id_required"})
            result = await accounts.disable_church_access(cid)
            return _json_payload(result)

        if tool_name == "reinstate_church_access":
            cid = (args.get("church_id") or "").strip()
            if not cid:
                return _json_payload({"error": "church_id_required"})
            result = await accounts.reinstate_church_access(cid)
            return _json_payload(result)

        if tool_name == "generate_subscription_report":
            report = await accounts.generate_subscription_report()
            return _json_payload(report)

        if tool_name == "notify_support_team":
            alert = (args.get("alert") or "").strip()
            if not alert:
                return _json_payload({"error": "alert_required"})
            payload_nt = {"alert": alert}
            early, resolved = _gate_outbound(
                session_id,
                tool_name,
                args,
                payload_nt,
                "support_escalation",
            )
            if early:
                return early
            alert = str(resolved["alert"])
            result = await accounts.notify_support_team(alert)
            return _json_payload(result)

        if tool_name == "get_stalled_expense_requests":
            cid = _resolve_church_id(args, church_hint)
            hours = int(args.get("hours") or 48)
            stalled = await treasury.get_stalled_expense_requests(
                church_id=cid,
                hours=hours,
            )
            return _json_payload(
                {
                    "church_id": cid,
                    "hours": hours,
                    "count": len(stalled),
                    "requests": stalled[:80],
                }
            )

        if tool_name == "get_stalled_programs":
            cid = _resolve_church_id(args, church_hint)
            hours = int(args.get("hours") or 72)
            stalled = await departments.get_stalled_programs(hours=hours)
            if cid:
                stalled = [
                    p
                    for p in stalled
                    if str(p.get("church_id") or "") == cid
                    or str((p.get("church") or {}).get("id") or "") == cid
                ]
            return _json_payload(
                {"church_id": cid, "hours": hours, "count": len(stalled), "programs": stalled[:80]}
            )

        if tool_name == "get_upcoming_activities":
            cid, meta = await _resolve_church_for_scope(args, church_hint)
            if meta.get("church_name_resolution") == "ambiguous":
                return _json_payload({"error": "ambiguous_church_name", **meta})
            if meta.get("church_name_resolution") == "no_match":
                return _json_payload({"error": "church_not_found", **meta})
            if not cid:
                return _json_payload(
                    {
                        "error": "church_scope_required",
                        "detail": "Provide church_id, church_name, or scope the dashboard to a church.",
                    }
                )
            days = min(max(int(args.get("days") or 7), 1), 365)
            acts = await departments.get_upcoming_activities(church_id=cid, days=days)
            return _json_payload(
                {"resolution": meta, "church_id": cid, "days": days, "count": len(acts), "activities": acts[:150]}
            )

        if tool_name == "get_pending_program_approvals":
            cid, meta = await _resolve_church_for_scope(args, church_hint)
            if meta.get("church_name_resolution") == "ambiguous":
                return _json_payload({"error": "ambiguous_church_name", **meta})
            if meta.get("church_name_resolution") == "no_match":
                return _json_payload({"error": "church_not_found", **meta})
            if not cid:
                return _json_payload(
                    {
                        "error": "church_scope_required",
                        "detail": "Provide church_id, church_name, or scope the dashboard to a church.",
                    }
                )
            rep = await departments.get_pending_program_approvals(cid)
            return _json_payload({"resolution": meta, **rep})

        if tool_name == "get_department_budget_status":
            cid, meta = await _resolve_church_for_scope(args, church_hint)
            if meta.get("church_name_resolution") == "ambiguous":
                return _json_payload({"error": "ambiguous_church_name", **meta})
            if meta.get("church_name_resolution") == "no_match":
                return _json_payload({"error": "church_not_found", **meta})
            if not cid:
                return _json_payload(
                    {
                        "error": "church_scope_required",
                        "detail": "Provide church_id, church_name, or scope the dashboard to a church.",
                    }
                )
            rep = await departments.get_department_budget_status(cid)
            return _json_payload({"resolution": meta, **rep})

        if tool_name == "get_department_members":
            dept_id = (args.get("department_id") or "").strip()
            if not dept_id:
                return _json_payload({"error": "department_id_required"})
            data = await departments.get_department_members(dept_id)
            return _json_payload(data)

        if tool_name == "get_program_details":
            pid = (args.get("program_id") or "").strip()
            if not pid:
                return _json_payload({"error": "program_id_required"})
            detail = await departments.get_program_details(pid)
            return _json_payload({"program_id": pid, "program": detail})

        if tool_name == "get_program_approval_history":
            pid = (args.get("program_id") or "").strip()
            if not pid:
                return _json_payload({"error": "program_id_required"})
            hist = await departments.get_program_approval_history(pid)
            return _json_payload(hist)

        if tool_name == "get_activity_detail":
            dept_id = (args.get("department_id") or "").strip()
            act_id = (args.get("activity_id") or "").strip()
            if not dept_id or not act_id:
                return _json_payload({"error": "department_id_and_activity_id_required"})
            detail = await departments.get_activity_detail(dept_id, act_id)
            return _json_payload({"department_id": dept_id, "activity_id": act_id, "activity": detail})

        if tool_name == "notify_department_head":
            dept_id = (args.get("department_id") or "").strip()
            msg = (args.get("message") or "").strip()
            if not dept_id or not msg:
                return _json_payload({"error": "department_id_and_message_required"})
            cid, meta = await _resolve_church_for_scope(args, church_hint)
            if meta.get("church_name_resolution") == "ambiguous":
                return _json_payload({"error": "ambiguous_church_name", **meta})
            if meta.get("church_name_resolution") == "no_match":
                return _json_payload({"error": "church_not_found", **meta})
            preview_r = await departments.resolve_department_head_email(dept_id)
            if preview_r.get("error"):
                return _json_payload({**preview_r, "resolution": meta})
            to_em = preview_r.get("email")
            if not to_em:
                return _json_payload(
                    {
                        "error": "department_head_email_missing",
                        "department_id": dept_id,
                        "head_member_id": preview_r.get("head_member_id"),
                        "resolution": meta,
                    }
                )
            dlabel = preview_r.get("department_name") or dept_id
            subj = ((args.get("subject") or "").strip() or f"Department notice — {dlabel}")[:200]
            payload_ndh = {
                "to": to_em,
                "subject": subj,
                "body": msg,
                "church_id": cid,
                "department_id": dept_id,
                "department_name": preview_r.get("department_name"),
            }
            early, resolved = _gate_outbound(
                session_id,
                tool_name,
                args,
                payload_ndh,
                "department_head_email",
            )
            if early:
                return early
            try:
                result = await departments.notify_department_head(
                    str(resolved["department_id"]),
                    str(resolved["body"]),
                    subject=str(resolved["subject"]),
                    church_id=resolved.get("church_id"),
                )
                out_ndh: dict[str, Any] = dict(result) if isinstance(result, dict) else {"result": result}
                out_ndh["resolution"] = meta
                return _json_payload(out_ndh)
            except Exception as e:
                logger.warning("notify_department_head failed: %s", e)
                err_ndh: dict[str, Any] = {"error": str(e)}
                if looks_like_auth_or_scope_error(e):
                    err_ndh["configuration_help"] = auth_configuration_message()
                return _json_payload(err_ndh)

        if tool_name == "send_activity_reminder":
            dept_id = (args.get("department_id") or "").strip()
            act_id = (args.get("activity_id") or "").strip()
            extra_raw = args.get("extra_message")
            extra = (str(extra_raw).strip() if extra_raw is not None else "") or None
            if not dept_id or not act_id:
                return _json_payload({"error": "department_id_and_activity_id_required"})
            cid, meta = await _resolve_church_for_scope(args, church_hint)
            if meta.get("church_name_resolution") == "ambiguous":
                return _json_payload({"error": "ambiguous_church_name", **meta})
            if meta.get("church_name_resolution") == "no_match":
                return _json_payload({"error": "church_not_found", **meta})
            act = await departments.get_activity_detail(dept_id, act_id)
            if isinstance(act, dict) and act.get("detail"):
                return _json_payload(
                    {"error": "activity_not_found", "detail": act.get("detail"), "resolution": meta}
                )
            title = (act.get("title") if isinstance(act, dict) else None) or "Activity"
            preview_r = await departments.resolve_department_head_email(dept_id)
            if preview_r.get("error"):
                return _json_payload({**preview_r, "resolution": meta})
            to_em = preview_r.get("email")
            if not to_em:
                return _json_payload(
                    {
                        "error": "department_head_email_missing",
                        "department_id": dept_id,
                        "head_member_id": preview_r.get("head_member_id"),
                        "resolution": meta,
                    }
                )
            subj = f"Activity reminder — {title}"[:200]
            payload_sar = {
                "to": to_em,
                "subject": subj,
                "church_id": cid,
                "department_id": dept_id,
                "activity_id": act_id,
                "extra_message": extra,
                "department_name": preview_r.get("department_name"),
                "activity_title": title,
            }
            early, resolved = _gate_outbound(
                session_id,
                tool_name,
                args,
                payload_sar,
                "activity_reminder_email",
            )
            if early:
                return early
            try:
                ex = resolved.get("extra_message")
                if isinstance(ex, str) and not ex.strip():
                    ex = None
                result = await departments.send_activity_reminder(
                    str(resolved["department_id"]),
                    str(resolved["activity_id"]),
                    church_id=resolved.get("church_id"),
                    extra_message=ex if isinstance(ex, str) else None,
                )
                out_sar: dict[str, Any] = dict(result) if isinstance(result, dict) else {"result": result}
                out_sar["resolution"] = meta
                return _json_payload(out_sar)
            except Exception as e:
                logger.warning("send_activity_reminder failed: %s", e)
                err_sar: dict[str, Any] = {"error": str(e)}
                if looks_like_auth_or_scope_error(e):
                    err_sar["configuration_help"] = auth_configuration_message()
                return _json_payload(err_sar)

        if tool_name == "get_treasury_statistics":
            cid, meta = await _resolve_church_for_scope(args, church_hint)
            if meta.get("church_name_resolution") == "ambiguous":
                return _json_payload({"error": "ambiguous_church_name", **meta})
            if meta.get("church_name_resolution") == "no_match":
                return _json_payload({"error": "church_not_found", **meta})
            if not cid:
                return _json_payload(
                    {
                        "error": "church_scope_required",
                        "detail": "Provide church_id, church_name, or scope the dashboard to a church.",
                    }
                )
            stats = await treasury.get_treasury_stats(church_id=cid)
            return _json_payload({"church_id": cid, "resolution": meta, "statistics": stats})

        if tool_name == "get_income_summary":
            cid, meta = await _resolve_church_for_scope(args, church_hint)
            if meta.get("church_name_resolution") == "ambiguous":
                return _json_payload({"error": "ambiguous_church_name", **meta})
            if meta.get("church_name_resolution") == "no_match":
                return _json_payload({"error": "church_not_found", **meta})
            if not cid:
                return _json_payload(
                    {
                        "error": "church_scope_required",
                        "detail": "Provide church_id, church_name, or dashboard church scope.",
                    }
                )
            sd = (args.get("start_date") or "").strip() or None
            ed = (args.get("end_date") or "").strip() or None
            days = min(max(int(args.get("days") or 30), 1), 730)
            summary = await treasury.get_income_summary(cid, start_date=sd, end_date=ed, days=days)
            return _json_payload({"resolution": meta, **summary})

        if tool_name == "get_expense_summary":
            cid, meta = await _resolve_church_for_scope(args, church_hint)
            if meta.get("church_name_resolution") == "ambiguous":
                return _json_payload({"error": "ambiguous_church_name", **meta})
            if meta.get("church_name_resolution") == "no_match":
                return _json_payload({"error": "church_not_found", **meta})
            if not cid:
                return _json_payload(
                    {
                        "error": "church_scope_required",
                        "detail": "Provide church_id, church_name, or dashboard church scope.",
                    }
                )
            sd = (args.get("start_date") or "").strip() or None
            ed = (args.get("end_date") or "").strip() or None
            days = min(max(int(args.get("days") or 30), 1), 730)
            summary = await treasury.get_expense_summary(cid, start_date=sd, end_date=ed, days=days)
            return _json_payload({"resolution": meta, **summary})

        if tool_name == "detect_anomalies":
            cid, meta = await _resolve_church_for_scope(args, church_hint)
            if meta.get("church_name_resolution") == "ambiguous":
                return _json_payload({"error": "ambiguous_church_name", **meta})
            if meta.get("church_name_resolution") == "no_match":
                return _json_payload({"error": "church_not_found", **meta})
            if not cid:
                return _json_payload(
                    {
                        "error": "church_scope_required",
                        "detail": "Provide church_id, church_name, or dashboard church scope.",
                    }
                )
            thr = args.get("threshold")
            threshold = float(thr) if thr is not None else None
            days = min(max(int(args.get("days") or 7), 1), 90)
            found = await treasury.detect_anomalies(cid, threshold=threshold, days=days)
            return _json_payload({"resolution": meta, **found})

        if tool_name == "get_budget_vs_actual":
            cid, meta = await _resolve_church_for_scope(args, church_hint)
            if meta.get("church_name_resolution") == "ambiguous":
                return _json_payload({"error": "ambiguous_church_name", **meta})
            if meta.get("church_name_resolution") == "no_match":
                return _json_payload({"error": "church_not_found", **meta})
            if not cid:
                return _json_payload(
                    {
                        "error": "church_scope_required",
                        "detail": "Provide church_id, church_name, or dashboard church scope.",
                    }
                )
            dept_id = (args.get("department_id") or "").strip()
            if not dept_id:
                return _json_payload({"error": "department_id_required"})
            report = await treasury.get_budget_vs_actual(cid, dept_id)
            return _json_payload({"resolution": meta, **report})

        if tool_name == "get_asset_inventory":
            cid, meta = await _resolve_church_for_scope(args, church_hint)
            if meta.get("church_name_resolution") == "ambiguous":
                return _json_payload({"error": "ambiguous_church_name", **meta})
            if meta.get("church_name_resolution") == "no_match":
                return _json_payload({"error": "church_not_found", **meta})
            if not cid:
                return _json_payload(
                    {
                        "error": "church_scope_required",
                        "detail": "Provide church_id, church_name, or dashboard church scope.",
                    }
                )
            ps = min(int(args.get("page_size") or 200), 500)
            inv = await treasury.get_asset_inventory(cid, page_size=ps)
            return _json_payload({"resolution": meta, **inv})

        if tool_name == "generate_financial_report":
            cid, meta = await _resolve_church_for_scope(args, church_hint)
            if meta.get("church_name_resolution") == "ambiguous":
                return _json_payload({"error": "ambiguous_church_name", **meta})
            if meta.get("church_name_resolution") == "no_match":
                return _json_payload({"error": "church_not_found", **meta})
            if not cid:
                return _json_payload(
                    {
                        "error": "church_scope_required",
                        "detail": "Provide church_id, church_name, or dashboard church scope.",
                    }
                )
            rf = (args.get("format") or "json").strip()
            year = args.get("year")
            month = args.get("month")
            yi = int(year) if year is not None else None
            mi = int(month) if month is not None else None
            report = await treasury.generate_financial_report(
                cid,
                report_format=rf,
                year=yi,
                month=mi,
            )
            return _json_payload({"resolution": meta, **report})

        if tool_name == "send_treasurer_alert":
            cid, meta = await _resolve_church_for_scope(args, church_hint)
            if meta.get("church_name_resolution") == "ambiguous":
                return _json_payload({"error": "ambiguous_church_name", **meta})
            if meta.get("church_name_resolution") == "no_match":
                return _json_payload({"error": "church_not_found", **meta})
            if not cid:
                return _json_payload(
                    {
                        "error": "church_scope_required",
                        "detail": "Provide church_id, church_name, or dashboard church scope.",
                    }
                )
            msg = (args.get("message") or "").strip()
            if not msg:
                return _json_payload({"error": "message_required"})
            church = await accounts.get_church(cid)
            to_override = (args.get("to_email") or "").strip()
            to_addr = to_override or (church.get("email") if isinstance(church, dict) else None) or ""
            to_addr = str(to_addr).strip()
            if not to_addr:
                return _json_payload(
                    {
                        "error": "no_recipient",
                        "detail": "Set to_email or ensure the church record has an email address.",
                    }
                )
            cname = (church.get("name") if isinstance(church, dict) else None) or cid
            subj = ((args.get("subject") or "").strip() or f"Treasury notice — {cname}")[:200]
            payload_ta = {
                "to": to_addr,
                "subject": subj,
                "body": msg,
                "church_id": cid,
            }
            early, resolved = _gate_outbound(
                session_id,
                tool_name,
                args,
                payload_ta,
                "treasurer_email",
            )
            if early:
                return early
            try:
                result = await notifications.send_email(
                    to=str(resolved["to"]),
                    subject=str(resolved["subject"]),
                    body=str(resolved["body"]),
                    church_id=str(resolved.get("church_id") or cid),
                )
                return _json_payload(
                    {
                        "status": "ok",
                        "resolution": meta,
                        "recipient": resolved["to"],
                        "django_response": result,
                    }
                )
            except Exception as e:
                logger.warning("send_treasurer_alert failed: %s", e)
                err_ta: dict[str, Any] = {"error": str(e)}
                if looks_like_auth_or_scope_error(e):
                    err_ta["configuration_help"] = auth_configuration_message()
                return _json_payload(err_ta)

        if tool_name in ("get_member_stats", "query_member_stats"):
            cid, meta = await _resolve_church_for_scope(args, church_hint)
            if meta.get("church_name_resolution") == "ambiguous":
                return _json_payload({"error": "ambiguous_church_name", **meta})
            if meta.get("church_name_resolution") == "no_match":
                return _json_payload({"error": "church_not_found", **meta})
            if not cid:
                return _json_payload(
                    {
                        "error": "church_scope_required",
                        "detail": "Provide church_id, church_name, or scope the dashboard to a church.",
                    }
                )
            stats = await member_tools.get_member_stats(church_id=cid)
            return _json_payload({"church_id": cid, "resolution": meta, "stats": stats})

        if tool_name == "get_member_profile":
            mid = (args.get("member_id") or "").strip()
            if not mid:
                return _json_payload({"error": "member_id_required"})
            prof = await member_tools.get_member_profile(mid)
            return _json_payload({"member_id": mid, "profile": prof})

        if tool_name == "get_new_members":
            cid, meta = await _resolve_church_for_scope(args, church_hint)
            if meta.get("church_name_resolution") == "ambiguous":
                return _json_payload({"error": "ambiguous_church_name", **meta})
            if meta.get("church_name_resolution") == "no_match":
                return _json_payload({"error": "church_not_found", **meta})
            if not cid:
                return _json_payload(
                    {
                        "error": "church_scope_required",
                        "detail": "Provide church_id, church_name, or scope the dashboard to a church.",
                    }
                )
            days = min(int(args.get("days") or 7), 365)
            rows = await member_tools.get_new_members(cid, days=days)
            return _json_payload(
                {"church_id": cid, "resolution": meta, "days": days, "count": len(rows), "members": rows[:120]}
            )

        if tool_name == "convert_visitor_to_member":
            vid = (args.get("visitor_id") or "").strip()
            ms = (args.get("member_since") or "").strip()
            if not vid or not ms:
                return _json_payload({"error": "visitor_id_and_member_since_required"})
            occ = (args.get("occupation") or "").strip()
            notes = (args.get("notes") or "").strip()
            r = await member_tools.convert_visitor_to_member(vid, ms, occupation=occ, notes=notes)
            return _json_payload({"result": r})

        if tool_name == "search_members":
            cid, meta = await _resolve_church_for_scope(args, church_hint)
            if meta.get("church_name_resolution") == "ambiguous":
                return _json_payload({"error": "ambiguous_church_name", **meta})
            if meta.get("church_name_resolution") == "no_match":
                return _json_payload({"error": "church_not_found", **meta})
            if not cid:
                return _json_payload(
                    {
                        "error": "church_scope_required",
                        "detail": "Provide church_id, church_name, or scope the dashboard to a church.",
                    }
                )
            query = (args.get("query") or "").strip().lower()
            limit = min(int(args.get("limit") or 40), 100)
            members = await member_tools.get_members(church_id=cid)
            out = []
            for m in members:
                blob = " ".join(
                    [
                        str(m.get("first_name", "")),
                        str(m.get("last_name", "")),
                        str(m.get("email", "")),
                    ]
                ).lower()
                if not query or query in blob:
                    out.append(
                        {
                            "id": m.get("id"),
                            "first_name": m.get("first_name"),
                            "last_name": m.get("last_name"),
                            "email": m.get("email"),
                            "status": m.get("status"),
                        }
                    )
                if len(out) >= limit:
                    break
            return _json_payload(
                {
                    "church_id": cid,
                    "query": query,
                    "match_count": len(out),
                    "members": out,
                }
            )

        if tool_name == "get_church_overview":
            cid, meta = await _resolve_church_for_scope(args, church_hint)
            if meta.get("church_name_resolution") == "ambiguous":
                return _json_payload({"error": "ambiguous_church_name", **meta})
            if meta.get("church_name_resolution") == "no_match":
                return _json_payload({"error": "church_not_found", **meta})
            if not cid:
                return _json_payload(
                    {
                        "error": "church_scope_required",
                        "detail": "Provide church_id, church_name, or scope the dashboard to a church.",
                    }
                )
            church = await accounts.get_church(cid)
            stats = await member_tools.get_member_stats(church_id=cid)
            tstats = await treasury.get_treasury_stats(church_id=cid)
            depts = await departments.get_departments(church_id=cid)
            programs = await departments.get_programs(church_id=cid)
            stalled_exp = await treasury.get_stalled_expense_requests(church_id=cid)
            stalled_prog_all = await departments.get_stalled_programs()
            stalled_prog = [
                p
                for p in stalled_prog_all
                if str(p.get("church_id") or "") == cid
                or str((p.get("church") or {}).get("id") or "") == cid
            ]
            return _json_payload(
                {
                    "church_id": cid,
                    "resolution": meta,
                    "church": church,
                    "member_stats": stats,
                    "treasury_stats": tstats,
                    "department_count": len(depts) if isinstance(depts, list) else 0,
                    "program_count": len(programs) if isinstance(programs, list) else 0,
                    "stalled_expense_requests_count": len(stalled_exp),
                    "stalled_programs_count": len(stalled_prog),
                }
            )

        if tool_name == "get_system_status":
            partial: dict[str, Any] = {"partial_errors": []}
            churches: list = []
            try:
                raw = await accounts.get_all_churches(page=1, page_size=500)
                churches = raw if isinstance(raw, list) else []
            except Exception as e:
                partial["partial_errors"].append(f"get_all_churches: {e}")
            tenant_count = len(churches)
            expiring: list = []
            try:
                expiring = await accounts.get_expiring_subscriptions(days=7)
            except Exception as e:
                partial["partial_errors"].append(f"get_expiring_subscriptions: {e}")
            stalled_exp: list = []
            try:
                stalled_exp = await treasury.get_stalled_expense_requests()
            except Exception as e:
                partial["partial_errors"].append(f"get_stalled_expense_requests: {e}")
            stalled_prog: list = []
            try:
                stalled_prog = await departments.get_stalled_programs()
            except Exception as e:
                partial["partial_errors"].append(f"get_stalled_programs: {e}")
            out_sys = {
                "tenant_count_cap500": tenant_count,
                "expiring_subscriptions_7d": len(expiring),
                "stalled_expense_requests_global": len(stalled_exp),
                "stalled_programs_global": len(stalled_prog),
            }
            if partial["partial_errors"]:
                out_sys["partial_errors"] = partial["partial_errors"]
            return _json_payload(out_sys)

        if tool_name == "generate_daily_briefing":
            status_raw = await run_orchestrator_tool(
                "get_system_status",
                "{}",
                church_hint=church_hint,
                jwt_ok=jwt_ok,
                session_id=session_id,
            )
            status = json.loads(status_raw)
            briefing: dict[str, Any] = {"system": status, "church": None}
            cid, scope_meta = await _resolve_church_for_scope(args, church_hint)
            briefing["church_resolution"] = scope_meta if scope_meta else None

            if scope_meta.get("church_name_resolution") == "ambiguous":
                briefing["hints"] = [
                    "Ask the user which candidate church they meant (list candidates by name).",
                    "Summarize platform-wide risks from system section.",
                ]
                return _json_payload(briefing)

            if cid:
                ov_raw = await run_orchestrator_tool(
                    "get_church_overview",
                    json.dumps({"church_id": cid}),
                    church_hint=church_hint,
                    jwt_ok=jwt_ok,
                    session_id=session_id,
                )
                briefing["church"] = json.loads(ov_raw)
            elif scope_meta.get("church_name_resolution") == "no_match":
                briefing["hints"] = [
                    "No church matched that name — suggest get_church_directory or a clearer name.",
                    "Summarize platform-wide metrics from system.",
                ]
            else:
                briefing["hints"] = [
                    "Summarize risks (expiring subs, stalled approvals) from system.",
                    "If the user named a church, pass church_name into this tool (not only free text).",
                ]
            return _json_payload(briefing)

        if tool_name == "query_knowledge_base":
            q = (args.get("question") or "").strip()
            if not q:
                return _json_payload({"error": "question_required"})
            n = min(max(int(args.get("n_results") or 8), 1), 20)
            cid = (args.get("church_id") or "").strip() or church_hint
            try:
                from memory import vector_store

                chunks = vector_store.query(q, n_results=n, church_id=cid or None)
                if not chunks:
                    chunks = []
                return _json_payload(
                    {
                        "chunks": chunks,
                        "church_id_filter": cid,
                        "note": (
                            "Empty result if Chroma has no docs — use live API tools for operational data."
                        ),
                    }
                )
            except Exception as e:
                logger.warning("RAG query failed: %s", e)
                return _json_payload({"chunks": [], "error": str(e)})

        if tool_name == "list_pending_tasks":
            cid = _resolve_church_id(args, church_hint)
            errs: list[str] = []
            alerts_raw: list = []
            try:
                raw_al = await agent_data.list_agent_alerts(60)
                alerts_raw = raw_al if isinstance(raw_al, list) else []
            except Exception as e:
                errs.append(f"list_agent_alerts: {e}")
                alerts_raw = []
            stalled_exp: list = []
            try:
                stalled_exp = await treasury.get_stalled_expense_requests(church_id=cid)
            except Exception as e:
                errs.append(f"get_stalled_expense_requests: {e}")
            pending_exp: list = []
            try:
                pending_exp = await treasury.get_pending_expense_requests(church_id=cid)
            except Exception as e:
                errs.append(f"get_pending_expense_requests: {e}")
            stalled_prog: list = []
            try:
                stalled_prog = await departments.get_stalled_programs()
            except Exception as e:
                errs.append(f"get_stalled_programs: {e}")
            if cid:
                stalled_prog = [
                    p
                    for p in stalled_prog
                    if str(p.get("church_id") or "") == cid
                    or str((p.get("church") or {}).get("id") or "") == cid
                ]
            expiring: list = []
            try:
                expiring = await accounts.get_expiring_subscriptions(days=7)
            except Exception as e:
                errs.append(f"get_expiring_subscriptions: {e}")
            trials: list = []
            try:
                trials = await accounts.get_trial_churches()
            except Exception as e:
                errs.append(f"get_trial_churches: {e}")
            slim_alerts = []
            for a in alerts_raw[:40]:
                if not isinstance(a, dict):
                    continue
                slim_alerts.append(
                    {
                        "severity": a.get("severity"),
                        "message": a.get("message"),
                        "agent_name": a.get("agent_name"),
                        "church_id": a.get("church_id"),
                    }
                )
            out_pt: dict[str, Any] = {
                "church_id_scope": cid,
                "agent_alerts": slim_alerts,
                "stalled_expense_requests": {
                    "count": len(stalled_exp),
                    "sample": stalled_exp[:12],
                },
                "pending_submitted_expenses": {
                    "count": len(pending_exp),
                    "sample": pending_exp[:10],
                },
                "stalled_programs": {
                    "count": len(stalled_prog),
                    "sample": stalled_prog[:12],
                },
                "expiring_subscriptions_next_7d_count": len(expiring),
                "trial_or_free_church_count": len(trials),
            }
            if errs:
                out_pt["partial_errors"] = errs
            return _json_payload(out_pt)

        if tool_name == "get_audit_logs":
            cid = (args.get("church_id") or "").strip() or None
            act = (args.get("action_type") or "").strip() or None
            rng = (args.get("range") or "week").strip()
            ps = min(int(args.get("page_size") or 100), 100)
            data = await audit_tools.get_audit_logs(
                church_id=cid, action_type=act, range_token=rng, page_size=ps
            )
            return _json_payload(data if isinstance(data, dict) else {"results": data})

        if tool_name == "get_failed_login_attempts":
            th = int(args.get("threshold") or 5)
            cid = (args.get("church_id") or "").strip() or None
            out = await audit_tools.get_failed_login_attempts(threshold=th, church_id=cid)
            return _json_payload(out)

        if tool_name == "get_permission_changes":
            cid = (args.get("church_id") or "").strip() or None
            rng = (args.get("range") or "month").strip()
            out = await audit_tools.get_permission_changes(church_id=cid, range_token=rng)
            return _json_payload(out)

        if tool_name == "get_locked_accounts":
            cid = (args.get("church_id") or "").strip() or None
            rows = await audit_tools.get_locked_accounts(church_id=cid)
            return _json_payload({"count": len(rows), "locked_users": rows[:200]})

        if tool_name == "flag_suspicious_activity":
            det = (args.get("details") or "").strip()
            if not det:
                return _json_payload({"error": "details_required"})
            cid = (args.get("church_id") or "").strip() or None
            at = (args.get("alert_type") or "SUSPICIOUS_ACTIVITY").strip()
            sev = (args.get("severity") or "WARNING").strip()
            r = await audit_tools.flag_suspicious_activity(
                church_id=cid, details=det, alert_type=at, severity=sev
            )
            return _json_payload(r if isinstance(r, dict) else {"result": r})

        if tool_name == "generate_audit_report":
            cid = (args.get("church_id") or "").strip() or None
            rng = (args.get("range") or "month").strip()
            rep = await audit_tools.generate_audit_report(church_id=cid, range_token=rng)
            return _json_payload(rep)

        if tool_name == "send_security_alert":
            to_addr = (args.get("admin_email") or "").strip()
            msg = (args.get("message") or "").strip()
            subj = (args.get("subject") or "").strip() or None
            if not to_addr or not msg:
                return _json_payload({"error": "admin_email_and_message_required"})
            payload_sa2 = {"admin_email": to_addr, "message": msg, "subject": subj}
            early, resolved = _gate_outbound(
                session_id,
                tool_name,
                args,
                payload_sa2,
                "security_alert_email",
            )
            if early:
                return early
            to_addr = str(resolved["admin_email"])
            msg = str(resolved["message"])
            subj = resolved.get("subject")
            r = await audit_tools.send_security_alert(
                admin_email=to_addr, message=msg, subject=subj if subj else None
            )
            return _json_payload(r if isinstance(r, dict) else {"result": r})

        if tool_name == "detect_bulk_actions":
            cid = (args.get("church_id") or "").strip() or None
            th = int(args.get("threshold") or 10)
            wm = int(args.get("window_minutes") or 5)
            out = await audit_tools.detect_bulk_actions(
                church_id=cid, threshold=th, window_minutes=wm
            )
            return _json_payload(out)

        if tool_name == "handoff_to_agent":
            from agents.agent_handoff import run_full_agent_if_enabled
            from agents.specialist_snapshots import normalize_agent_key, run_specialist_snapshot

            raw_name = (args.get("agent_name") or "").strip()
            if not raw_name:
                return _json_payload({"error": "agent_name_required"})
            task = (args.get("task") or "").strip()
            nk = normalize_agent_key(raw_name)
            if args.get("execute_full_run"):
                out = await run_full_agent_if_enabled(nk, task)
                return _json_payload(out)
            snap = await run_specialist_snapshot(raw_name, task)
            return _json_payload(snap)

        if tool_name == "gather_specialist_insights":
            from agents.specialist_snapshots import gather_specialist_insights as gather_si

            names = args.get("agent_names")
            keys: list[str] | None = None
            if isinstance(names, list) and names:
                keys = [str(x) for x in names]
            merged = await gather_si(keys)
            return _json_payload(merged)

        if tool_name == "analytics_members_joined_last_month":
            cid, meta = await _resolve_church_for_scope(args, church_hint)
            if meta.get("church_name_resolution") == "ambiguous":
                return _json_payload({"error": "ambiguous_church_name", **meta})
            if meta.get("church_name_resolution") == "no_match":
                return _json_payload({"error": "church_not_found", **meta})
            if not cid:
                return _json_payload(
                    {
                        "error": "church_scope_required",
                        "detail": "Provide church_id or church_name or dashboard church scope.",
                    }
                )
            stats = await member_tools.count_members_joined_last_calendar_month(cid)
            return _json_payload({"resolution": meta, "report": stats})

        if tool_name == "analytics_financial_month":
            year = int(args.get("year") or 0)
            month = int(args.get("month") or 0)
            if year < 2000 or month < 1 or month > 12:
                return _json_payload({"error": "invalid_year_month"})
            cid, meta = await _resolve_church_for_scope(args, church_hint)
            if meta.get("church_name_resolution") == "ambiguous":
                return _json_payload({"error": "ambiguous_church_name", **meta})
            if meta.get("church_name_resolution") == "no_match":
                return _json_payload({"error": "church_not_found", **meta})
            inc = await treasury.sum_income_for_calendar_month(year, month, church_id=cid)
            exp = await treasury.sum_expenses_for_calendar_month(year, month, church_id=cid)
            return _json_payload(
                {"resolution": meta, "income": inc, "expenses": exp}
            )

        if tool_name == "list_trial_plan_churches":
            trials = await accounts.get_trial_churches()
            slim = [
                {"id": c.get("id"), "name": c.get("name"), "plan": c.get("subscription_plan")}
                for c in (trials if isinstance(trials, list) else [])
            ]
            return _json_payload({"count": len(slim), "churches": slim})

        if tool_name == "send_notification_email":
            to_addr = (args.get("to") or "").strip()
            subject = (args.get("subject") or "").strip()
            body = (args.get("body") or "").strip()
            cid_mail = (
                (args.get("church_id") or "").strip()
                or (church_hint or "").strip()
                or None
            )
            if not to_addr or not subject or not body:
                return _json_payload({"error": "to_subject_and_body_required"})
            payload_ne = {
                "to": to_addr,
                "subject": subject,
                "body": body,
                "church_id": cid_mail,
            }
            early, resolved = _gate_outbound(
                session_id,
                tool_name,
                args,
                payload_ne,
                "email",
            )
            if early:
                return early
            try:
                result = await notifications.send_email(
                    to=str(resolved["to"]),
                    subject=str(resolved["subject"]),
                    body=str(resolved["body"]),
                    church_id=resolved.get("church_id"),
                )
                return _json_payload({"status": "ok", "django_response": result})
            except Exception as e:
                logger.warning("send_notification_email failed: %s", e)
                err: dict[str, Any] = {"error": str(e)}
                if looks_like_auth_or_scope_error(e):
                    err["configuration_help"] = auth_configuration_message()
                return _json_payload(err)

        if tool_name == "send_sms_to_number":
            phone = (args.get("phone_number") or "").strip()
            msg = (args.get("message") or "").strip()
            if not phone or not msg:
                return _json_payload({"error": "phone_number_and_message_required"})
            cid_sms = (
                (args.get("church_id") or "").strip()
                or (church_hint or "").strip()
                or None
            )
            payload_sms = {"phone_number": phone, "message": msg, "church_id": cid_sms}
            early, resolved = _gate_outbound(
                session_id,
                tool_name,
                args,
                payload_sms,
                "sms",
            )
            if early:
                return early
            try:
                result = await notifications.send_sms(
                    to_phone=str(resolved["phone_number"]),
                    message=str(resolved["message"]),
                    church_id=resolved.get("church_id"),
                )
                return _json_payload({"status": "ok", "django_response": result})
            except Exception as e:
                logger.warning("send_sms_to_number failed: %s", e)
                err_sms: dict[str, Any] = {"error": str(e)}
                if looks_like_auth_or_scope_error(e):
                    err_sms["configuration_help"] = auth_configuration_message()
                return _json_payload(err_sms)

        if tool_name == "send_birthday_greetings":
            import os as _os

            from agents.outbound_approval import approval_required

            cid, meta = await _resolve_church_for_scope(args, church_hint)
            if meta.get("church_name_resolution") == "ambiguous":
                return _json_payload({"error": "ambiguous_church_name", **meta})
            if meta.get("church_name_resolution") == "no_match":
                return _json_payload({"error": "church_not_found", **meta})
            if not cid:
                return _json_payload(
                    {
                        "error": "church_scope_required",
                        "detail": "Church scope required for birthday greetings.",
                    }
                )
            bday = await member_tools.get_birthdays_today(church_id=cid)
            church = await accounts.get_church(cid)
            cname = (church.get("name") if isinstance(church, dict) else None) or "your church"
            preview = [
                {
                    "member_id": m.get("id"),
                    "email": m.get("email"),
                    "name": f"{m.get('first_name', '')} {m.get('last_name', '')}".strip(),
                }
                for m in (bday if isinstance(bday, list) else [])
            ]
            allow_env = _os.getenv("BIRTHDAY_GREETINGS_ALLOW_SEND", "").lower() in (
                "1",
                "true",
                "yes",
            )

            if approval_required() and (session_id or "").strip():
                pload_bg = {
                    "church_id": cid,
                    "church_name": cname,
                    "would_email_preview": preview[:80],
                }
                early_bg, resolved_bg = _gate_outbound(
                    session_id,
                    tool_name,
                    args,
                    pload_bg,
                    "birthday_emails_batch",
                )
                if early_bg:
                    return early_bg
                cid = str(resolved_bg["church_id"])
                bday = await member_tools.get_birthdays_today(church_id=cid)
                church = await accounts.get_church(cid)
                cname = (church.get("name") if isinstance(church, dict) else None) or "your church"

            confirm = bool(args.get("confirm_send"))
            if not confirm or not allow_env:
                preview_fresh = [
                    {
                        "member_id": m.get("id"),
                        "email": m.get("email"),
                        "name": f"{m.get('first_name', '')} {m.get('last_name', '')}".strip(),
                    }
                    for m in (bday if isinstance(bday, list) else [])
                ]
                return _json_payload(
                    {
                        "dry_run": True,
                        "church_id": cid,
                        "birthday_count": len(preview_fresh),
                        "would_email": preview_fresh,
                        "note": (
                            "Set confirm_send=true and BIRTHDAY_GREETINGS_ALLOW_SEND=true "
                            "to send messages via Django notifications."
                        ),
                    }
                )
            sent = []
            errors = []
            for m in bday if isinstance(bday, list) else []:
                to = (m.get("email") or "").strip()
                if not to:
                    errors.append({"member_id": m.get("id"), "error": "no_email"})
                    continue
                fn = m.get("first_name") or "Friend"
                try:
                    await notifications.send_email(
                        to=to,
                        subject=f"Happy Birthday, {fn}! — {cname}",
                        body=(
                            f"Warm birthday greetings from everyone at {cname}!\n\n"
                            f"We're grateful for you and pray for a blessed year ahead."
                        ),
                        church_id=cid,
                    )
                    sent.append(to)
                except Exception as e:
                    errors.append({"email": to, "error": str(e)})
            return _json_payload(
                {
                    "dry_run": False,
                    "sent_count": len(sent),
                    "sent_to": sent,
                    "errors": errors,
                }
            )

        return _json_payload({"error": "unknown_tool", "tool_name": tool_name})

    except Exception as e:
        logger.warning("Tool %s failed: %s", tool_name, e)
        err = {"error": str(e), "tool": tool_name}
        if looks_like_auth_or_scope_error(e):
            err["configuration_help"] = auth_configuration_message()
        return _json_payload(err)
