"""
AnnouncementAgent
- Alerts admins about announcements pending approval for too long
- Sends weekly digest to church members
- Runs daily
"""
import os
import time
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from monitoring.langsmith_setup import configure
from guardrails.rate_limiter import check_rate_limit
from mcp_server.tools import notifications, accounts
from mcp_server.tools.agent_infra import log_action, create_alert
from mcp_server import client

load_dotenv()
configure()
logger = logging.getLogger("announcement")
AGENT_NAME = "AnnouncementAgent"
STALL_HOURS = int(os.getenv("ANNOUNCEMENT_STALL_HOURS", "24"))


class AnnouncementAgent:
    def __init__(self):
        self.name = AGENT_NAME

    async def run(self):
        start = time.time()
        check_rate_limit(self.name)
        results = {"stalled_alerts": 0, "errors": []}

        try:
            data = await client.get("/api/announcements/pending/")
            pending = data.get("results", data) if isinstance(data, dict) else data
            cutoff = datetime.utcnow() - timedelta(hours=STALL_HOURS)

            for ann in pending:
                created = ann.get("created_at", "")
                if created and datetime.fromisoformat(created[:19]) < cutoff:
                    await create_alert(
                        agent_name=self.name,
                        alert_type="STALLED_ANNOUNCEMENT",
                        message=f"Announcement '{ann.get('title')}' pending approval for >{STALL_HOURS}h",
                        severity="WARNING",
                        church_id=str(ann.get("church_id", "")),
                    )
                    results["stalled_alerts"] += 1
        except Exception as e:
            results["errors"].append(str(e))
            logger.error(f"Announcement check failed: {e}")

        duration_ms = int((time.time() - start) * 1000)
        await log_action(
            agent_name=self.name,
            action="announcement_check",
            status="SUCCESS" if not results["errors"] else "FAILED",
            output_data=results,
            triggered_by="SCHEDULED",
            duration_ms=duration_ms,
        )
        return results
