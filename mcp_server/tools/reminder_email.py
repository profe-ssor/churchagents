"""Shared subscription renewal reminder email body (used by MCP tools + watchdog)."""
import os


def build_renewal_reminder_email(church: dict, days_left: int) -> tuple[str, str]:
    """Return (subject, body) for a subscription expiry reminder."""
    name = church.get("name", "Church")
    subject = (
        f"[Action Required] Your ChurchSaaS subscription expires in {days_left} "
        f"day{'s' if days_left != 1 else ''}"
    )
    body = f"""
Dear {name} Administrator,

This is an automated reminder that your ChurchSaaS subscription will expire in {days_left} day{'s' if days_left != 1 else ''}.

Subscription Details:
  - Church: {name}
  - Plan: {church.get("subscription_plan", "N/A")}
  - Expiry Date: {church.get("subscription_expiry") or church.get("subscription_end_date") or church.get("subscription_ends_at", "N/A")}

To avoid any interruption to your service, please renew your subscription before the expiry date.

Renew now: {os.getenv("DJANGO_BASE_URL", "")}/billing/

If you have already renewed, please disregard this message.

Best regards,
ChurchSaaS Support Team
{os.getenv("SUPPORT_TEAM_EMAIL", "")}
""".strip()
    return subject, body
