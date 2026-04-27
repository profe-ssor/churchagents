"""
MCP Tools — Departments & Programs
Endpoints: /api/departments/  /api/programs/
"""
from __future__ import annotations

from datetime import datetime, timedelta

from mcp_server import client


# Programs in an approval workflow (not yet APPROVED / terminal).
_PENDING_APPROVAL_STATUSES = frozenset(
    ("SUBMITTED", "ELDER_APPROVED", "SECRETARIAT_APPROVED", "TREASURY_APPROVED")
)


async def get_departments(church_id: str = None) -> list:
    params = {}
    if church_id:
        params["church_id"] = church_id
    data = await client.get("/api/departments/", params=params)
    return data.get("results", data) if isinstance(data, dict) else data


async def get_department(dept_id: str) -> dict:
    return await client.get(f"/api/departments/{dept_id}/")


async def get_programs(
    church_id: str | None = None,
    status: str | None = None,
    page_size: int = 200,
) -> list:
    params: dict[str, str] = {"page_size": str(min(max(page_size, 1), 500))}
    if church_id:
        params["church_id"] = church_id
    if status:
        params["status"] = status
    data = await client.get("/api/programs/", params=params)
    return data.get("results", data) if isinstance(data, dict) else data


async def get_pending_programs() -> list:
    """Programs submitted but not yet approved."""
    return await get_programs(status="SUBMITTED", page_size=500)


async def get_stalled_programs(hours: int = 72) -> list:
    """Programs pending approval longer than `hours` hours."""
    programs = await get_pending_programs()
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    stalled = []
    for p in programs:
        submitted = p.get("submitted_at") or p.get("created_at", "")
        if submitted:
            dt = datetime.fromisoformat(submitted[:19])
            if dt < cutoff:
                p["hours_pending"] = int((datetime.utcnow() - dt).total_seconds() / 3600)
                stalled.append(p)
    return stalled


async def get_upcoming_activities(church_id: str = None, days: int = 7) -> list:
    """Return department activities happening in the next `days` days."""
    depts = await get_departments(church_id=church_id)
    upcoming = []
    from datetime import date
    today = date.today()
    cutoff = today + timedelta(days=days)
    for dept in depts:
        dept_id = dept.get("id")
        try:
            acts = await client.get(
                f"/api/departments/{dept_id}/activities/",
                params={"time_filter": "upcoming"}
            )
            acts = acts.get("results", acts) if isinstance(acts, dict) else acts
            for a in acts:
                act_date = (
                    a.get("start_date") or a.get("date") or a.get("event_date") or ""
                )
                if act_date and date.fromisoformat(str(act_date)[:10]) <= cutoff:
                    a["department_name"] = dept.get("name")
                    upcoming.append(a)
        except Exception:
            continue
    return upcoming


async def get_pending_program_approvals(church_id: str) -> dict:
    """Programs awaiting approval steps (workflow statuses before full APPROVED)."""
    programs = await get_programs(church_id=church_id, page_size=500)
    if not isinstance(programs, list):
        programs = []
    pending = [
        p
        for p in programs
        if str(p.get("status") or "").upper() in _PENDING_APPROVAL_STATUSES
    ]
    return {
        "church_id": church_id,
        "count": len(pending),
        "programs": pending[:200],
        "statuses_included": sorted(_PENDING_APPROVAL_STATUSES),
    }


async def get_department_budget_status(church_id: str) -> dict:
    """Per-department program budget utilization (delegates to treasury.scan_department_budget_pressure)."""
    from mcp_server.tools import treasury as treasury_tools

    rows = await treasury_tools.scan_department_budget_pressure(church_id)
    return {
        "church_id": church_id,
        "department_count_flagged": len(rows),
        "departments": rows,
        "note": (
            "Utilization = sum(program expenses)/sum(program income) per department when income > 0; "
            "threshold from TREASURY_BUDGET_UTILIZATION_WARN (see treasury agent)."
        ),
    }


async def get_department_members(department_id: str) -> dict:
    """Members assigned to a department via MemberDepartment."""
    data = await client.get(f"/api/departments/{department_id}/members/")
    rows = data.get("results", data) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        rows = []
    return {"department_id": department_id, "count": len(rows), "members": rows}


async def get_program_details(program_id: str) -> dict:
    """Full program record including budget_items when returned by Django."""
    return await client.get(f"/api/programs/{program_id}/")


def synthesize_program_approval_history(program: dict) -> dict:
    """
    Build a coarse approval timeline from Program detail fields (no separate audit table in API).
    """
    pid = program.get("id")
    events: list[dict] = []

    def add(ev: str, at: object | None, detail: str | None = None) -> None:
        if not at:
            return
        events.append({"event": ev, "at": at, "detail": detail})

    add("created", program.get("created_at"), None)
    add("submitted", program.get("submitted_at"), None)
    add("approved_final", program.get("approved_at"), None)

    ap = program.get("approval_status")
    if isinstance(ap, dict):
        add("secretariat_approved", ap.get("secretariat_approved_at"), None)
        add("treasury_approved", ap.get("treasury_approved_at"), None)

    for key in (
        "secretariat_approved_at",
        "treasury_approved_at",
        "elder_approved_at",
        "rejected_at",
    ):
        if program.get(key):
            add(key, program.get(key), None)

    # Sort by timestamp string (ISO)
    def sort_key(e: dict) -> str:
        return str(e.get("at") or "")

    events.sort(key=sort_key)
    return {
        "program_id": pid,
        "current_status": program.get("status"),
        "events": events,
        "note": (
            "Synthetic trail from timestamp fields on the program record; "
            "use Django admin for full audit if available."
        ),
    }


async def get_program_approval_history(program_id: str) -> dict:
    """Approval-oriented view: program detail + synthesized timeline."""
    detail = await get_program_details(program_id)
    if isinstance(detail, dict) and detail.get("error"):
        return detail
    hist = synthesize_program_approval_history(detail if isinstance(detail, dict) else {})
    hist["program_summary"] = {
        "title": (detail if isinstance(detail, dict) else {}).get("title"),
        "status": (detail if isinstance(detail, dict) else {}).get("status"),
        "department_name": (detail if isinstance(detail, dict) else {}).get(
            "department_name"
        ),
    }
    return hist


async def get_activity_detail(department_id: str, activity_id: str) -> dict:
    return await client.get(
        f"/api/departments/{department_id}/activities/{activity_id}/"
    )


async def _primary_department_head_member_id(dept: dict) -> str | None:
    heads = dept.get("heads") or []
    if not isinstance(heads, list):
        return None
    for h in heads:
        if not isinstance(h, dict):
            continue
        role = str(h.get("head_role") or "")
        if role.endswith("HEAD") or role == "HEAD":
            mid = h.get("id")
            if mid:
                return str(mid)
    if heads and isinstance(heads[0], dict) and heads[0].get("id"):
        return str(heads[0]["id"])
    return None


async def _member_email(member_id: str) -> str | None:
    from mcp_server.tools import members as member_tools

    try:
        prof = await member_tools.get_member_profile(member_id)
        if not isinstance(prof, dict):
            return None
        loc = prof.get("location") if isinstance(prof.get("location"), dict) else {}
        em = (loc.get("email") or prof.get("email") or "").strip()
        return em or None
    except Exception:
        return None


async def resolve_department_head_email(department_id: str) -> dict:
    """Resolve primary department head member id + email for previews / outbound approval."""
    dept = await get_department(department_id)
    mid = await _primary_department_head_member_id(dept)
    if not mid:
        return {
            "error": "department_head_not_found",
            "department_id": department_id,
        }
    em = await _member_email(mid)
    return {
        "department_id": department_id,
        "department_name": dept.get("name"),
        "head_member_id": mid,
        "email": em,
    }


async def notify_department_head(
    department_id: str,
    message: str,
    subject: str | None = None,
    church_id: str | None = None,
) -> dict:
    """
    Email the primary department head (from department heads list + member profile).
    """
    from mcp_server.tools import notifications

    dept = await get_department(department_id)
    dname = (dept.get("name") or department_id).strip()
    mid = await _primary_department_head_member_id(dept)
    if not mid:
        return {
            "error": "department_head_not_found",
            "department_id": department_id,
            "detail": "No HEAD row on department; cannot resolve recipient.",
        }
    to_email = await _member_email(mid)
    if not to_email:
        return {
            "error": "department_head_email_missing",
            "member_id": mid,
            "detail": "Member record has no email on file.",
        }
    subj = (subject or "").strip() or f"Department notice — {dname}"
    cid = church_id or ""
    if not cid:
        ch = dept.get("church")
        if isinstance(ch, dict):
            cid = str(ch.get("id") or "")
        elif ch:
            cid = str(ch)
    await notifications.send_email(
        to=to_email,
        subject=subj[:200],
        body=message.strip(),
        church_id=cid or None,
    )
    return {
        "status": "sent",
        "department_id": department_id,
        "recipient_member_id": mid,
        "recipient_email": to_email,
    }


async def send_activity_reminder(
    department_id: str,
    activity_id: str,
    church_id: str | None = None,
    extra_message: str | None = None,
) -> dict:
    """
    Email the department head with a pre-event reminder for one activity.
    """
    act = await get_activity_detail(department_id, activity_id)
    if isinstance(act, dict) and act.get("detail"):
        return {"error": "activity_not_found", "detail": act.get("detail")}
    title = (act.get("title") if isinstance(act, dict) else None) or "Activity"
    start = (
        act.get("start_date")
        if isinstance(act, dict)
        else None
    ) or ""
    loc = (act.get("location") if isinstance(act, dict) else None) or ""
    dept_name = (act.get("department_name") if isinstance(act, dict) else None) or ""
    body_lines = [
        f"Reminder: upcoming department activity — {title}",
        f"Date: {start}",
    ]
    if loc:
        body_lines.append(f"Location: {loc}")
    if dept_name:
        body_lines.append(f"Department: {dept_name}")
    if extra_message:
        body_lines.append("")
        body_lines.append(extra_message.strip())
    body = "\n".join(body_lines)
    subj = f"Activity reminder — {title}"[:200]
    return await notify_department_head(
        department_id,
        body,
        subject=subj,
        church_id=church_id,
    )
