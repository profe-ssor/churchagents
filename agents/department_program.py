"""
DepartmentProgramAgent
- Detects stalled program approvals
- Sends reminders for upcoming department activities
- Runs every 12 hours
"""
import os
import time
import logging
from dotenv import load_dotenv
from monitoring.langsmith_setup import configure
from monitoring.alert_thresholds import PROGRAM_STALL_HOURS
from guardrails.rate_limiter import check_rate_limit
from mcp_server.tools import departments
from mcp_server.tools.agent_infra import log_action, create_alert

load_dotenv()
configure()
logger = logging.getLogger("department_program")
AGENT_NAME = "DepartmentProgramAgent"
ADMIN_EMAIL = os.getenv("PLATFORM_ADMIN_EMAIL", "admin@example.com")


class DepartmentProgramAgent:
    def __init__(self):
        self.name = AGENT_NAME

    async def run(self):
        start = time.time()
        check_rate_limit(self.name)
        results = {"stalled": 0, "reminders": 0, "errors": []}

        # 1. Stalled programs
        try:
            stalled = await departments.get_stalled_programs(hours=PROGRAM_STALL_HOURS)
            for prog in stalled:
                await create_alert(
                    agent_name=self.name,
                    alert_type="STALLED_PROGRAM",
                    message=f"Program '{prog.get('name', prog.get('id'))}' stalled {prog.get('hours_pending')}h",
                    severity="WARNING",
                    church_id=str(prog.get("church_id", "")),
                )
                results["stalled"] += 1
        except Exception as e:
            results["errors"].append(str(e))

        # 2. Upcoming activity reminders
        try:
            upcoming = await departments.get_upcoming_activities(days=3)
            for activity in upcoming:
                dept_name = activity.get("department_name", "Your Department")
                await create_alert(
                    agent_name=self.name,
                    alert_type="UPCOMING_ACTIVITY",
                    message=f"'{activity.get('title')}' by {dept_name} on {activity.get('date')}",
                    severity="INFO",
                    church_id=str(activity.get("church_id", "")),
                )
                results["reminders"] += 1
        except Exception as e:
            results["errors"].append(str(e))

        duration_ms = int((time.time() - start) * 1000)
        await log_action(
            agent_name=self.name,
            action="department_program_check",
            status="SUCCESS" if not results["errors"] else "FAILED",
            output_data=results,
            triggered_by="SCHEDULED",
            duration_ms=duration_ms,
        )
        return results
