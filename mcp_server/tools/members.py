"""
MCP Tools — Members & Visitors
Endpoints: /api/members/members/  /api/members/visitors/
"""
from calendar import monthrange

from mcp_server import client
from datetime import date, timedelta


def _church_id_from_record(record: dict) -> str | None:
    raw = record.get("church_id") or record.get("church")
    if raw is None:
        return None
    if isinstance(raw, dict):
        return str(raw.get("id") or "")
    return str(raw)


def _visitor_first_visit_date(v: dict) -> date | None:
    raw = v.get("first_visit_date") or v.get("visit_date")
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


async def get_members(church_id: str = None, status: str = None) -> list:
    """List members. Filter by church_id and/or status (ACTIVE, INACTIVE)."""
    params = {}
    if church_id:
        params["church_id"] = church_id
    if status:
        params["status"] = status
    data = await client.get("/api/members/members/", params=params)
    return data.get("results", data) if isinstance(data, dict) else data


async def get_member(member_id: str) -> dict:
    return await client.get(f"/api/members/members/{member_id}/")


async def get_inactive_members(church_id: str, days: int = 30) -> list:
    """Return members with no activity in the last `days` days."""
    members = await get_members(church_id=church_id, status="ACTIVE")
    cutoff = date.today() - timedelta(days=days)
    inactive = []
    for m in members:
        last = m.get("last_attendance") or m.get("updated_at", "")
        if last and date.fromisoformat(last[:10]) < cutoff:
            inactive.append(m)
    return inactive


async def get_members_with_birthdays(
    church_id: str | None = None,
    target_date: date | None = None,
) -> list:
    """Members whose birthday (month-day) matches target_date (default: today)."""
    td = target_date or date.today()
    mmdd = td.strftime("%m-%d")
    members = await get_members(church_id=church_id)
    out = []
    for m in members:
        dob = m.get("date_of_birth")
        if not dob or len(str(dob)) < 10:
            continue
        if str(dob)[5:10] == mmdd:
            out.append(m)
    return out


async def get_birthdays_today(church_id: str = None) -> list:
    """Return members whose birthday is today."""
    return await get_members_with_birthdays(church_id=church_id, target_date=date.today())


async def get_visitors(church_id: str = None) -> list:
    """List visitors."""
    params = {}
    if church_id:
        params["church_id"] = church_id
    data = await client.get("/api/members/visitors/", params=params)
    return data.get("results", data) if isinstance(data, dict) else data


async def get_recent_visitors(church_id: str, days: int = 7) -> list:
    """Return visitors whose first visit was within the last `days` days."""
    visitors = await get_visitors(church_id=church_id)
    cutoff = date.today() - timedelta(days=days)
    out = []
    for v in visitors:
        vd = _visitor_first_visit_date(v)
        if vd and vd >= cutoff:
            out.append(v)
    return out


async def get_visitors_due_for_followup(church_id: str, days_after_first_visit: int) -> list:
    """
    Unconverted visitors whose first_visit_date was exactly `days_after_first_visit` calendar days ago
    (use with VISITOR_FOLLOWUP_DAYS e.g. 3 → D+3 email, 7 → D+7 email without duplicate sends).
    """
    visitors = await get_visitors(church_id=church_id)
    target_day = date.today() - timedelta(days=days_after_first_visit)
    out = []
    for v in visitors:
        if v.get("converted_to_member"):
            continue
        vd = _visitor_first_visit_date(v)
        if vd == target_day:
            out.append(v)
    return out


async def get_unconverted_visitors(church_id: str, days_since_visit: int = 0) -> list:
    """
    Visitors not yet converted to members.
    If days_since_visit > 0, only those whose first visit was at least that many days ago.
    """
    visitors = await get_visitors(church_id=church_id)
    today = date.today()
    out = []
    for v in visitors:
        if v.get("converted_to_member"):
            continue
        vd = _visitor_first_visit_date(v)
        if not vd:
            continue
        age_days = (today - vd).days
        if age_days >= days_since_visit:
            out.append(v)
    return out


def member_join_date(m: dict) -> date | None:
    for key in ("created_at", "date_joined", "joined_at", "registration_date"):
        raw = m.get(key)
        if raw:
            try:
                return date.fromisoformat(str(raw)[:10])
            except ValueError:
                continue
    return None


async def count_members_joined_between(
    church_id: str,
    start: date,
    end: date,
) -> dict:
    """Members whose join/registration date falls in [start, end] inclusive."""
    members = await get_members(church_id=church_id)
    n = 0
    for m in members:
        jd = member_join_date(m)
        if jd and start <= jd <= end:
            n += 1
    return {
        "church_id": church_id,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "count": n,
    }


async def count_members_joined_last_calendar_month(church_id: str) -> dict:
    """How many members joined during the previous calendar month."""
    today = date.today()
    if today.month == 1:
        y, m = today.year - 1, 12
    else:
        y, m = today.year, today.month - 1
    start = date(y, m, 1)
    end = date(y, m, monthrange(y, m)[1])
    return await count_members_joined_between(church_id, start, end)


async def get_member_stats(church_id: str) -> dict:
    """Return member count breakdown by status."""
    members = await get_members(church_id=church_id)
    stats = {"total": len(members), "active": 0, "inactive": 0, "visitor": 0}
    for m in members:
        status = m.get("status", "").upper()
        if status == "ACTIVE":
            stats["active"] += 1
        elif status == "INACTIVE":
            stats["inactive"] += 1
    visitors = await get_visitors(church_id=church_id)
    stats["visitor"] = len(visitors)
    return stats


async def query_member_stats(church_id: str) -> dict:
    """Alias for tooling that names the call `query_member_stats`."""
    return await get_member_stats(church_id)


async def get_member_profile(member_id: str) -> dict:
    """Alias for full member detail (`get_member`)."""
    return await get_member(member_id)


async def get_new_members(church_id: str, days: int = 7) -> list:
    """Members whose join / registration date falls within the last `days` days."""
    members = await get_members(church_id=church_id)
    cutoff = date.today() - timedelta(days=days)
    out = []
    for m in members:
        jd = member_join_date(m)
        if jd and jd >= cutoff:
            out.append(m)
    return out


async def get_visitor(visitor_id: str) -> dict:
    return await client.get(f"/api/members/visitors/{visitor_id}/")


async def convert_visitor_to_member(
    visitor_id: str,
    member_since_iso: str,
    occupation: str = "",
    notes: str = "",
) -> dict:
    """
    POST /api/members/visitors/convert-to-member/
    member_since_iso: YYYY-MM-DD
    """
    payload: dict = {
        "visitor_id": visitor_id,
        "member_since": member_since_iso[:10],
    }
    if occupation:
        payload["occupation"] = occupation
    if notes:
        payload["notes"] = notes
    return await client.post("/api/members/visitors/convert-to-member/", payload)


async def send_birthday_email(member_id: str) -> dict:
    """Single-member birthday send (same tone as MemberCareAgent templates)."""
    from mcp_server.tools import member_care_templates as T
    from mcp_server.tools import accounts as accounts_tools
    from mcp_server.tools import notifications

    m = await get_member(member_id)
    cid = _church_id_from_record(m)
    if not cid:
        return {"error": "church_not_found", "member_id": member_id}
    church = await accounts_tools.get_church(cid)
    cname = (church.get("name") if isinstance(church, dict) else None) or "your church"
    fn = (m.get("first_name") or "Friend").strip()
    to = (m.get("email") or "").strip()
    if not to:
        return {"error": "no_email", "member_id": member_id}
    body = T.birthday_body(fn, cname)
    subj = f"Happy Birthday, {fn}! — {cname}"
    return await notifications.send_email(to, subj, body, church_id=cid)


async def send_welcome_email(member_id: str) -> dict:
    """Welcome email for a member record (onboarding)."""
    from mcp_server.tools import member_care_templates as T
    from mcp_server.tools import accounts as accounts_tools
    from mcp_server.tools import notifications

    m = await get_member(member_id)
    cid = _church_id_from_record(m)
    if not cid:
        return {"error": "church_not_found", "member_id": member_id}
    church = await accounts_tools.get_church(cid)
    cname = (church.get("name") if isinstance(church, dict) else None) or "your church"
    fn = (m.get("first_name") or "Friend").strip()
    to = (m.get("email") or "").strip()
    if not to:
        return {"error": "no_email", "member_id": member_id}
    body = T.welcome_body(fn, cname)
    subj = f"Welcome to {cname}!"
    return await notifications.send_email(to, subj, body, church_id=cid)


async def send_visitor_followup(visitor_id: str, days_since_visit: int = 7) -> dict:
    """
    Follow-up email to one visitor. Template picks D+3 / D+7 style when days_since_visit matches.
    """
    from mcp_server.tools import member_care_templates as T
    from mcp_server.tools import accounts as accounts_tools
    from mcp_server.tools import notifications

    v = await get_visitor(visitor_id)
    cid = _church_id_from_record(v)
    if not cid:
        return {"error": "church_not_found", "visitor_id": visitor_id}
    church = await accounts_tools.get_church(cid)
    cname = (church.get("name") if isinstance(church, dict) else None) or "your church"
    full = (v.get("full_name") or "Friend").strip()
    first = full.split()[0] if full else "Friend"
    to = (v.get("email") or "").strip()
    if not to:
        return {"error": "no_email", "visitor_id": visitor_id}
    if days_since_visit == 3:
        variant = "d3"
    elif days_since_visit == 7:
        variant = "d7"
    else:
        variant = "generic"
    body = T.visitor_followup_body(first, cname, days_since_visit, variant=variant)
    subj = f"We'd love to see you again at {cname}"
    return await notifications.send_email(to, subj, body, church_id=cid)


async def send_inactive_checkin_email(member_id: str) -> dict:
    """Polite check-in for a disengaged member (use sparingly; MemberCareAgent caps sends)."""
    from mcp_server.tools import member_care_templates as T
    from mcp_server.tools import accounts as accounts_tools
    from mcp_server.tools import notifications

    m = await get_member(member_id)
    cid = _church_id_from_record(m)
    if not cid:
        return {"error": "church_not_found", "member_id": member_id}
    church = await accounts_tools.get_church(cid)
    cname = (church.get("name") if isinstance(church, dict) else None) or "your church"
    fn = (m.get("first_name") or "Friend").strip()
    to = (m.get("email") or "").strip()
    if not to:
        return {"error": "no_email", "member_id": member_id}
    body = T.inactive_checkin_body(fn, cname)
    subj = f"We miss you at {cname}"
    return await notifications.send_email(to, subj, body, church_id=cid)
