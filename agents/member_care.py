"""
MemberCareAgent — member engagement & lifecycle

Scheduled work (preserved):
- Birthday emails (today)
- Visitor D+n follow-ups (VISITOR_FOLLOWUP_DAYS, exact calendar days since first visit)
- Inactive member digest (AgentAlert + optional capped check-in emails)

Optional env (see `.env.example`):
- MEMBER_CARE_SPLIT_INACTIVE_TO_SUNDAY — daily job skips inactive; use Sunday task only
- MEMBER_CARE_SEND_WELCOME_EMAIL — welcome email for members whose join date is today
- MEMBER_CARE_SEND_INACTIVE_CHECKIN_EMAIL — email inactive members directly (capped)
- MEMBER_CARE_TRANSFER_STATUS_ALERT — digest alert if anyone is in TRANSFER status
"""
import os
import time
import logging
from datetime import date

from dotenv import load_dotenv
from monitoring.langsmith_setup import configure
from monitoring.alert_thresholds import MEMBER_INACTIVE_DAYS, VISITOR_FOLLOWUP_DAYS
from guardrails.rate_limiter import check_rate_limit
from mcp_server.tools import members as member_tools, notifications, accounts
from mcp_server.tools import member_care_templates as tmpl
from mcp_server.tools.agent_infra import log_action, create_alert

load_dotenv()
configure()
logger = logging.getLogger("member_care")

AGENT_NAME = "MemberCareAgent"

SPLIT_INACTIVE_TO_SUNDAY = os.getenv("MEMBER_CARE_SPLIT_INACTIVE_TO_SUNDAY", "").lower() in (
    "1",
    "true",
    "yes",
)
SEND_WELCOME_EMAIL = os.getenv("MEMBER_CARE_SEND_WELCOME_EMAIL", "").lower() in ("1", "true", "yes")
SEND_INACTIVE_CHECKIN_EMAIL = os.getenv("MEMBER_CARE_SEND_INACTIVE_CHECKIN_EMAIL", "").lower() in (
    "1",
    "true",
    "yes",
)
INACTIVE_EMAIL_CAP_PER_RUN = max(0, int(os.getenv("MEMBER_CARE_INACTIVE_EMAIL_CAP_PER_RUN", "5")))
TRANSFER_STATUS_ALERT = os.getenv("MEMBER_CARE_TRANSFER_STATUS_ALERT", "").lower() in ("1", "true", "yes")


class MemberCareAgent:
    def __init__(self):
        self.name = AGENT_NAME

    async def run(self, inactive_scan_only: bool = False):
        """
        Daily run (default): birthdays, visitor follow-ups, optional welcome;
        inactive handling unless SPLIT_INACTIVE_TO_SUNDAY is enabled.

        inactive_scan_only=True: only inactive alerts / optional inactive emails (Sunday job).
        """
        start = time.time()
        logger.info(f"{self.name} starting (inactive_scan_only={inactive_scan_only})...")
        check_rate_limit(self.name)
        results = {
            "birthdays": 0,
            "visitor_followups": 0,
            "welcome_emails": 0,
            "inactive_members_flagged": 0,
            "inactive_emails_sent": 0,
            "transfer_digest": 0,
            "errors": [],
        }

        try:
            churches = await accounts.get_all_churches()
        except Exception as e:
            logger.error(f"Could not fetch churches: {e}")
            fail = {**results, "errors": [str(e)]}
            await self._finalize_log(start, fail)
            return fail

        if inactive_scan_only:
            if not SPLIT_INACTIVE_TO_SUNDAY:
                logger.info(
                    "%s inactive-only beat skipped (enable MEMBER_CARE_SPLIT_INACTIVE_TO_SUNDAY for Sunday inactive job)",
                    self.name,
                )
                return results
            for church in churches:
                church_id = str(church.get("id", ""))
                church_name = church.get("name", church_id)
                admin_email = church.get("email", "")
                await self._inactive_block(church_id, church_name, admin_email, results)
            await self._finalize_log(start, results)
            logger.info(f"{self.name} inactive-only done. {results}")
            return results

        for church in churches:
            church_id = str(church.get("id", ""))
            church_name = church.get("name", church_id)

            await self._birthdays(church_id, church, results)
            await self._visitor_followups(church_id, church, results)

            if SEND_WELCOME_EMAIL:
                await self._welcome_new(church_id, church, results)

            if not SPLIT_INACTIVE_TO_SUNDAY:
                admin_email = church.get("email", "")
                await self._inactive_block(church_id, church_name, admin_email, results)

            if TRANSFER_STATUS_ALERT:
                await self._transfer_digest(church_id, church_name, results)

        await self._finalize_log(start, results)
        logger.info(f"{self.name} done. {results}")
        return results

    async def run_inactive_scan_only(self):
        """Sunday / optional beat — inactive alerts (+ optional emails)."""
        return await self.run(inactive_scan_only=True)

    async def _birthdays(self, church_id: str, church: dict, results: dict):
        try:
            birthday_members = await member_tools.get_birthdays_today(church_id=church_id)
            for member in birthday_members:
                to = (member.get("email") or "").strip()
                if not to:
                    continue
                fn = (member.get("first_name") or "Friend").strip()
                body = tmpl.birthday_body(fn, church.get("name", "your church"))
                await notifications.send_email(
                    to=to,
                    subject=f"Happy Birthday, {fn}!",
                    body=body,
                    church_id=church_id,
                )
                results["birthdays"] += 1
        except Exception as e:
            results["errors"].append(f"Birthday {church_id}: {e}")
            logger.error(f"Birthday {church_id}: {e}")

    async def _visitor_followups(self, church_id: str, church: dict, results: dict):
        try:
            for n in VISITOR_FOLLOWUP_DAYS:
                due = await member_tools.get_visitors_due_for_followup(church_id, n)
                for v in due:
                    to = (v.get("email") or "").strip()
                    if not to:
                        continue
                    full = (v.get("full_name") or "Friend").strip()
                    first = full.split()[0] if full else "Friend"
                    variant = "d3" if n == 3 else "d7" if n == 7 else "generic"
                    body = tmpl.visitor_followup_body(
                        first, church.get("name", "your church"), n, variant=variant
                    )
                    await notifications.send_email(
                        to=to,
                        subject=f"We'd love to see you again at {church.get('name')}!",
                        body=body,
                        church_id=church_id,
                    )
                    results["visitor_followups"] += 1
        except Exception as e:
            results["errors"].append(f"Visitor {church_id}: {e}")
            logger.error(f"Visitor {church_id}: {e}")

    async def _welcome_new(self, church_id: str, church: dict, results: dict):
        try:
            members = await member_tools.get_members(church_id=church_id)
            today = date.today()
            for m in members:
                jd = member_tools.member_join_date(m)
                if jd != today:
                    continue
                to = (m.get("email") or "").strip()
                if not to:
                    continue
                fn = (m.get("first_name") or "Friend").strip()
                body = tmpl.welcome_body(fn, church.get("name", "your church"))
                await notifications.send_email(
                    to=to,
                    subject=f"Welcome to {church.get('name')}!",
                    body=body,
                    church_id=church_id,
                )
                results["welcome_emails"] += 1
        except Exception as e:
            results["errors"].append(f"Welcome {church_id}: {e}")
            logger.error(f"Welcome {church_id}: {e}")

    async def _inactive_block(
        self,
        church_id: str,
        church_name: str,
        admin_email: str,
        results: dict,
    ):
        try:
            inactive = await member_tools.get_inactive_members(
                church_id=church_id, days=MEMBER_INACTIVE_DAYS
            )
            if inactive:
                await create_alert(
                    agent_name=self.name,
                    alert_type="INACTIVE_MEMBERS",
                    message=f"{len(inactive)} members inactive for {MEMBER_INACTIVE_DAYS}+ days at {church_name}",
                    severity="INFO",
                    church_id=church_id,
                )
                results["inactive_members_flagged"] += len(inactive)

            if SEND_INACTIVE_CHECKIN_EMAIL and inactive:
                sent = 0
                for m in inactive[:INACTIVE_EMAIL_CAP_PER_RUN]:
                    to = (m.get("email") or "").strip()
                    if not to:
                        continue
                    fn = (m.get("first_name") or "Friend").strip()
                    body = tmpl.inactive_checkin_body(fn, church_name)
                    await notifications.send_email(
                        to=to,
                        subject=f"We miss you at {church_name}",
                        body=body,
                        church_id=church_id,
                    )
                    sent += 1
                results["inactive_emails_sent"] += sent
        except Exception as e:
            results["errors"].append(f"Inactive {church_id}: {e}")
            logger.error(f"Inactive {church_id}: {e}")

    async def _transfer_digest(self, church_id: str, church_name: str, results: dict):
        try:
            members = await member_tools.get_members(church_id=church_id)
            n = sum(1 for m in members if (m.get("membership_status") or "").upper() == "TRANSFER")
            if n:
                await create_alert(
                    agent_name=self.name,
                    alert_type="MEMBER_TRANSFER_STATUS",
                    message=f"{n} member(s) currently in TRANSFER status — review at {church_name}.",
                    severity="INFO",
                    church_id=church_id,
                )
                results["transfer_digest"] += 1
        except Exception as e:
            results["errors"].append(f"Transfer digest {church_id}: {e}")
            logger.error(f"Transfer digest {church_id}: {e}")

    async def _finalize_log(self, start: float, results: dict):
        duration_ms = int((time.time() - start) * 1000)
        errs = results.get("errors") or []
        await log_action(
            agent_name=self.name,
            action="member_care_run",
            status="SUCCESS" if not errs else "FAILED",
            output_data=results,
            triggered_by="SCHEDULED",
            duration_ms=duration_ms,
        )
