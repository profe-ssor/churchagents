"""
MCP Tools — Send Email / SMS via Django notifications app
Endpoints: /api/notifications/send-email/  /api/notifications/send-sms/

Django SendEmailSerializer expects: email_address, subject, message_html (see notifications app).
"""
import html
import logging

from mcp_server import client
from mcp_server.auth import get_agent_church_id
from guardrails.input_validator import validate_email_payload
from guardrails.output_validator import validate_email_output
from guardrails.dry_run import DRY_RUN

logger = logging.getLogger("notifications")


async def send_email(to: str, subject: str, body: str, church_id: str = None) -> dict:
    """Send an email via Django's notification system."""
    validate_email_payload({"to": to, "subject": subject, "body": body})
    validate_email_output(body)

    if DRY_RUN:
        logger.info(f"[DRY RUN] Email → {to} | {subject}")
        return {"status": "dry_run", "to": to, "subject": subject}

    # Match notifications.serializers.SendEmailSerializer (EmailField, subject max 200, message_html)
    safe_html = f'<pre style="white-space:pre-wrap;font-family:inherit">{html.escape(body)}</pre>'
    payload = {
        "email_address": to.strip(),
        "subject": (subject or "")[:200],
        "message_html": safe_html,
    }
    cid = (church_id or get_agent_church_id() or "").strip()
    if not cid:
        raise RuntimeError(
            "Missing church context for send-email: pass `church_id` on the tool call, "
            "or set `AGENT_JWT_CHURCH_ID` in churchagents `.env` (platform admin JWTs need "
            "`X-Church-ID`). Restart the orchestrator after editing `.env`."
        )
    extra = {"X-Church-ID": cid}

    return await client.post("/api/notifications/send-email/", payload, extra_headers=extra)


async def send_bulk_email(recipients: list[dict], subject: str, body: str) -> dict:
    """
    Send email to multiple recipients.
    recipients: [{"email": "...", "name": "..."}, ...]
    """
    if DRY_RUN:
        logger.info(f"[DRY RUN] Bulk email to {len(recipients)} recipients | {subject}")
        return {"status": "dry_run", "count": len(recipients)}

    payload = {
        "recipients": recipients,
        "subject": subject,
        "message": body,
        "notification_type": "EMAIL",
    }
    return await client.post("/api/notifications/send-bulk/", payload)


async def send_sms(to_phone: str, message: str, church_id: str | None = None) -> dict:
    """Send SMS via Twilio through Django."""
    if DRY_RUN:
        logger.info(f"[DRY RUN] SMS → {to_phone} | {message[:60]}")
        return {"status": "dry_run"}

    cid = (church_id or get_agent_church_id() or "").strip()
    if not cid:
        raise RuntimeError(
            "Missing church context for send-sms: pass `church_id` on the tool call, "
            "or set `AGENT_JWT_CHURCH_ID` in churchagents `.env` (platform admin JWTs need "
            "`X-Church-ID`). Restart the orchestrator after editing `.env`."
        )
    extra = {"X-Church-ID": cid}

    return await client.post(
        "/api/notifications/send-sms/",
        {"phone_number": to_phone, "message": message},
        extra_headers=extra,
    )
