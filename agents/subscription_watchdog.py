"""
SubscriptionWatchdogAgent
- Runs every 6 hours via Celery Beat
- Detects churches expiring in 7, 3, 1 days
- Sends email reminders
- Flags suspended/expired churches
"""
import os
import time
import logging
from dotenv import load_dotenv
from monitoring.langsmith_setup import configure
from monitoring.alert_thresholds import SUBSCRIPTION_ALERT_DAYS
from guardrails.rate_limiter import check_rate_limit
from mcp_server.tools import accounts, notifications
from mcp_server.tools.agent_infra import log_action, create_alert

from mcp_server.tools.reminder_email import build_renewal_reminder_email

load_dotenv()
configure()
logger = logging.getLogger("subscription_watchdog")

MODEL = os.getenv("OPENAI_MODEL_SIMPLE", "gpt-4.1-mini")
AGENT_NAME = "SubscriptionWatchdogAgent"


class SubscriptionWatchdogAgent:
    def __init__(self):
        self.name = AGENT_NAME

    async def run(self):
        start = time.time()
        logger.info(f"{self.name} starting run...")
        check_rate_limit(self.name)

        alerts_sent = 0
        errors = []

        for days in SUBSCRIPTION_ALERT_DAYS:
            try:
                expiring = await accounts.get_expiring_subscriptions(days=days)
                for church in expiring:
                    try:
                        subject, body = build_renewal_reminder_email(church, days)
                        await notifications.send_email(
                            to=church.get("email", ""),
                            subject=subject,
                            body=body,
                            church_id=str(church.get("id", "")),
                        )
                        await create_alert(
                            agent_name=self.name,
                            alert_type="SUBSCRIPTION_EXPIRY",
                            message=f"{church.get('name')} expires in {days} days",
                            severity="WARNING" if days > 1 else "CRITICAL",
                            church_id=str(church.get("id", "")),
                        )
                        alerts_sent += 1
                        logger.info(f"Alert sent: {church.get('name')} — {days} days")
                    except Exception as e:
                        errors.append(str(e))
                        logger.error(f"Failed for church {church.get('id')}: {e}")
            except Exception as e:
                errors.append(str(e))
                logger.error(f"Error fetching {days}-day expiring: {e}")

        duration_ms = int((time.time() - start) * 1000)
        await log_action(
            agent_name=self.name,
            action="subscription_check",
            status="SUCCESS" if not errors else "FAILED",
            output_data={"alerts_sent": alerts_sent, "errors": errors},
            triggered_by="SCHEDULED",
            duration_ms=duration_ms,
        )
        logger.info(f"{self.name} done. Alerts sent: {alerts_sent}")
        return {"alerts_sent": alerts_sent, "errors": errors}
