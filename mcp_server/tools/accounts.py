"""
MCP Tools — Accounts / Subscriptions
Endpoints: /api/auth/churches/  /api/auth/users/  /api/auth/payments/
"""
import os
from datetime import date, datetime, timedelta, timezone

from mcp_server import client
from mcp_server.auth import get_agent_church_id
from mcp_server.tools import agent_infra, notifications
from mcp_server.tools.reminder_email import build_renewal_reminder_email


async def get_all_churches(page: int = 1, page_size: int = 500) -> list:
    """List churches (platform admin: all tenants; church-scoped user: their church only)."""
    params = {"page": page, "page_size": page_size}
    data = await client.get("/api/auth/churches/", params=params)
    return data.get("results", data) if isinstance(data, dict) else data


async def get_church(church_id: str) -> dict:
    """Get a single church by UUID."""
    return await client.get(f"/api/auth/churches/{church_id}/")


async def get_expiring_subscriptions(days: int = 7, days_ahead: int | None = None) -> list:
    """
    Return churches whose subscription expires within `days` days.
    Prefer `days_ahead` when provided (alias for tooling that names the parameter that way).
    """
    horizon = days_ahead if days_ahead is not None else days
    churches = await get_all_churches()
    cutoff = date.today() + timedelta(days=horizon)
    today = date.today()
    expiring = []
    for c in churches:
        expiry_str = (
            c.get("subscription_expiry")
            or c.get("subscription_end_date")
            or c.get("subscription_ends_at")
        )
        if not expiry_str:
            continue
        expiry = date.fromisoformat(str(expiry_str)[:10])
        active_like = (
            (c.get("subscription_status") == "ACTIVE")
            or (c.get("status") in ("ACTIVE", "TRIAL"))
        )
        if today <= expiry <= cutoff and active_like:
            c["days_remaining"] = (expiry - today).days
            expiring.append(c)
    return expiring


async def get_suspended_churches() -> list:
    """Return all suspended/disabled churches."""
    churches = await get_all_churches()
    out = []
    for c in churches:
        st = c.get("subscription_status") or c.get("status") or ""
        if st in ("SUSPENDED", "DISABLED", "EXPIRED"):
            out.append(c)
        elif c.get("platform_access_enabled") is False:
            out.append(c)
    return out


async def get_trial_churches() -> list:
    """Return all churches on trial plans."""
    churches = await get_all_churches()
    return [c for c in churches if c.get("subscription_plan") in ("TRIAL", "FREE")]


async def disable_church_access(church_id: str) -> dict:
    """Suspend a church's platform access."""
    return await client.patch(
        f"/api/auth/churches/{church_id}/platform-access/",
        {"platform_access_enabled": False},
    )


async def reinstate_church_access(church_id: str) -> dict:
    """Re-enable a church's platform access after payment."""
    return await client.patch(
        f"/api/auth/churches/{church_id}/platform-access/",
        {"platform_access_enabled": True},
    )


async def get_failed_payments(page_size: int = 100) -> list:
    """Paystack-backed Payment rows with status FAILED."""
    data = await client.get(
        "/api/auth/payments/",
        params={"status": "FAILED", "page_size": str(page_size)},
    )
    if isinstance(data, dict):
        return data.get("results", [])
    return data if isinstance(data, list) else []


async def get_payment_history(church_id: str, page_size: int = 100) -> list:
    """Payment log for one church (reference, status, amounts)."""
    data = await client.get(
        "/api/auth/payments/",
        params={"church_id": church_id, "page_size": str(page_size)},
    )
    if isinstance(data, dict):
        return data.get("results", [])
    return data if isinstance(data, list) else []


async def send_renewal_reminder_email(church_id: str, days_left: int) -> dict:
    """Send templated expiry warning to the church admin email."""
    church = await get_church(church_id)
    if not church or not church.get("id"):
        return {"error": "church_not_found", "church_id": church_id}
    subject, body = build_renewal_reminder_email(church, days_left)
    to = (church.get("email") or "").strip()
    if not to:
        return {"error": "no_church_email", "church_id": church_id}
    return await notifications.send_email(
        to=to,
        subject=subject,
        body=body,
        church_id=str(church_id),
    )


async def send_sms_alert(church_id: str, message: str) -> dict:
    """SMS via Django notifications (Twilio/configured backend) using the church primary phone."""
    church = await get_church(church_id)
    if not church or not church.get("id"):
        return {"error": "church_not_found", "church_id": church_id}
    phone = (church.get("phone") or "").strip()
    if not phone:
        return {
            "error": "no_phone",
            "detail": "Church record has no phone number.",
            "church_id": church_id,
        }
    return await notifications.send_sms(
        to_phone=phone, message=message, church_id=str(church_id)
    )


async def generate_subscription_report() -> dict:
    """Aggregate tenant health: counts, expiring windows, failed payments."""
    churches = await get_all_churches(page_size=500)
    clist = churches if isinstance(churches, list) else []
    failed = await get_failed_payments(page_size=500)
    failed_list = failed if isinstance(failed, list) else []
    pending_pay = await client.get(
        "/api/auth/payments/",
        params={"status": "PENDING", "page_size": "500"},
    )
    pending_rows = (
        pending_pay.get("results", []) if isinstance(pending_pay, dict) else []
    )

    exp7 = await get_expiring_subscriptions(days_ahead=7)
    exp30 = await get_expiring_subscriptions(days_ahead=30)
    trials = await get_trial_churches()
    suspended = await get_suspended_churches()

    enabled = sum(
        1 for c in clist if c.get("platform_access_enabled") is not False
    )

    iso_now = datetime.now(timezone.utc).isoformat()
    return {
        "generated_at": iso_now,
        "tenant_count": len(clist),
        "platform_access_enabled_approx": enabled,
        "expiring_within_7_days": len(exp7),
        "expiring_within_30_days": len(exp30),
        "trial_or_free_churches": len(trials),
        "suspended_or_locked_churches": len(suspended),
        "failed_paystack_payments_count": len(failed_list),
        "pending_payments_count": len(pending_rows),
        "failed_payments_sample": failed_list[:25],
    }


async def notify_support_team(alert: str) -> dict:
    """Email SUPPORT_TEAM_EMAIL (if set) and create a CRITICAL AgentAlert."""
    text = (alert or "").strip()
    if not text:
        return {"error": "empty_alert"}

    church_id = get_agent_church_id()
    out: dict = {}
    support = (os.getenv("SUPPORT_TEAM_EMAIL") or "").strip()
    if support:
        out["email"] = await notifications.send_email(
            to=support,
            subject="[ChurchSaaS] Agent support escalation",
            body=text,
            church_id=church_id,
        )
    else:
        out["email"] = {"skipped": True, "reason": "SUPPORT_TEAM_EMAIL unset"}

    out["alert"] = await agent_infra.create_alert(
        agent_name="SubscriptionWatchdogAgent",
        alert_type="SUPPORT_ESCALATION",
        message=text[:8000],
        severity="CRITICAL",
        church_id=church_id,
    )
    return out


async def get_all_users(church_id: str = None) -> list:
    """List users, optionally filtered by church."""
    params = {}
    if church_id:
        params["church_id"] = church_id
    data = await client.get("/api/auth/users/", params=params)
    return data.get("results", data) if isinstance(data, dict) else data
