"""
SecretariatAgent
- Processes document requests (transfer letters, certificates)
- Generates meeting minutes summaries
- Runs on-demand and daily
"""
import os
import time
import logging
from dotenv import load_dotenv
from monitoring.langsmith_setup import configure
from guardrails.rate_limiter import check_rate_limit
from mcp_server.tools import secretariat, notifications
from mcp_server.tools.agent_infra import log_action, create_alert

load_dotenv()
configure()
logger = logging.getLogger("secretariat_agent")
AGENT_NAME = "SecretariatAgent"
ADMIN_EMAIL = os.getenv("PLATFORM_ADMIN_EMAIL", "admin@example.com")


class SecretariatAgent:
    def __init__(self):
        self.name = AGENT_NAME

    async def run(self):
        """Daily check for pending document requests."""
        start = time.time()
        check_rate_limit(self.name)
        results = {"pending_requests": 0, "errors": []}

        try:
            pending = await secretariat.get_document_requests(status="PENDING")
            for req in pending:
                await create_alert(
                    agent_name=self.name,
                    alert_type="PENDING_DOCUMENT",
                    message=f"Document request '{req.get('document_type', req.get('id'))}' pending for {req.get('requester_name', 'member')}",
                    severity="INFO",
                    church_id=str(req.get("church_id", "")),
                )
                results["pending_requests"] += 1
        except Exception as e:
            results["errors"].append(str(e))
            logger.error(f"Document request check failed: {e}")

        duration_ms = int((time.time() - start) * 1000)
        await log_action(
            agent_name=self.name,
            action="secretariat_daily_check",
            status="SUCCESS" if not results["errors"] else "FAILED",
            output_data=results,
            triggered_by="SCHEDULED",
            duration_ms=duration_ms,
        )
        return results

    async def generate_transfer_letter(self, member_id: str, destination_church: str, reason: str) -> dict:
        """On-demand: create a transfer letter for a member."""
        try:
            result = await secretariat.create_transfer_letter({
                "member_id": member_id,
                "destination_church": destination_church,
                "reason": reason,
            })
            await log_action(
                agent_name=self.name,
                action="generate_transfer_letter",
                status="SUCCESS",
                input_data={"member_id": member_id, "destination": destination_church},
                output_data=result,
                triggered_by="ON_DEMAND",
            )
            return result
        except Exception as e:
            logger.error(f"Transfer letter failed: {e}")
            await log_action(
                agent_name=self.name,
                action="generate_transfer_letter",
                status="FAILED",
                error=str(e),
                triggered_by="ON_DEMAND",
            )
            raise
