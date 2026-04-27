"""
TreasuryHealthAgent
- Monitors expense requests, stalled approvals, large transactions
- Runs every 12 hours
"""
import os
import time
import logging
from dotenv import load_dotenv
from monitoring.langsmith_setup import configure
from monitoring.alert_thresholds import (
    EXPENSE_STALL_HOURS,
    ANOMALY_AMOUNT,
    INCOME_STALE_DAYS,
)
from guardrails.rate_limiter import check_rate_limit
from mcp_server.tools import treasury, notifications, accounts
from mcp_server.tools.agent_infra import log_action, create_alert

load_dotenv()
configure()
logger = logging.getLogger("treasury_health")

MODEL = os.getenv("OPENAI_MODEL_COMPLEX", "gpt-4.1")
AGENT_NAME = "TreasuryHealthAgent"
ADMIN_EMAIL = os.getenv("PLATFORM_ADMIN_EMAIL", "admin@example.com")

# Optional: budget pressure + income-gap checks (same Alert pipeline; off by default)
TREASURY_EXTENDED_HEALTH_CHECKS = os.getenv("TREASURY_EXTENDED_HEALTH_CHECKS", "").lower() in (
    "1",
    "true",
    "yes",
)


class TreasuryHealthAgent:
    def __init__(self):
        self.name = AGENT_NAME

    async def run(self):
        start = time.time()
        logger.info(f"{self.name} starting run...")
        check_rate_limit(self.name)

        issues = []
        errors = []

        # Get all active churches — treasury endpoints require church_id
        try:
            churches = await accounts.get_all_churches()
        except Exception as e:
            errors.append(f"Could not fetch churches: {e}")
            churches = []

        for church in churches:
            church_id = str(church.get("id", ""))
            church_name = church.get("name", church_id)

            # 1. Check stalled expense requests per church
            try:
                stalled = await treasury.get_stalled_expense_requests(
                    church_id=church_id, hours=EXPENSE_STALL_HOURS
                )
                for req in stalled:
                    msg = (
                        f"[{church_name}] Expense request "
                        f"'{req.get('title', req.get('id'))}' pending "
                        f"{req.get('hours_pending')}h "
                        f"(Amount: {req.get('amount_requested', req.get('amount'))})"
                    )
                    await create_alert(
                        agent_name=self.name,
                        alert_type="STALLED_EXPENSE",
                        message=msg,
                        severity="WARNING",
                        church_id=church_id,
                    )
                    issues.append(msg)
                    logger.warning(f"Stalled expense: {msg}")
            except Exception as e:
                errors.append(f"Stalled check [{church_name}]: {e}")
                logger.error(f"Stalled expense check failed for {church_name}: {e}")

            # 2. Check for large/anomalous transactions per church
            try:
                large_txs = await treasury.get_large_transactions(
                    church_id=church_id, threshold=ANOMALY_AMOUNT
                )
                for tx in large_txs:
                    msg = (
                        f"[{church_name}] Large transaction: "
                        f"{tx.get('amount')} "
                        f"| {tx.get('description', 'No description')}"
                    )
                    await create_alert(
                        agent_name=self.name,
                        alert_type="ANOMALY_TRANSACTION",
                        message=msg,
                        severity="CRITICAL",
                        church_id=church_id,
                    )
                    issues.append(msg)
                    logger.warning(f"Anomaly: {msg}")
            except Exception as e:
                errors.append(f"Anomaly check [{church_name}]: {e}")
                logger.error(f"Anomaly check failed for {church_name}: {e}")

            if TREASURY_EXTENDED_HEALTH_CHECKS:
                try:
                    stale = await treasury.church_income_stale(
                        church_id, days=INCOME_STALE_DAYS
                    )
                    if stale:
                        msg = (
                            f"[{church_name}] No income transactions recorded in the last "
                            f"{INCOME_STALE_DAYS} days."
                        )
                        await create_alert(
                            agent_name=self.name,
                            alert_type="INCOME_STALE",
                            message=msg,
                            severity="WARNING",
                            church_id=church_id,
                        )
                        issues.append(msg)
                        logger.warning(f"Income gap: {msg}")
                except Exception as e:
                    errors.append(f"Income stale check [{church_name}]: {e}")
                    logger.error(f"Income stale check failed for {church_name}: {e}")

                try:
                    pressured = await treasury.scan_department_budget_pressure(church_id)
                    for row in pressured:
                        msg = (
                            f"[{church_name}] Department {row.get('department_name') or row.get('department_id')}: "
                            f"program budget spend vs income ≈ {float(row.get('utilization', 0)):.0%} "
                            f"(expenses {row.get('total_expenses')} vs income {row.get('total_income')})."
                        )
                        await create_alert(
                            agent_name=self.name,
                            alert_type="BUDGET_UTILIZATION",
                            message=msg,
                            severity="WARNING",
                            church_id=church_id,
                        )
                        issues.append(msg)
                        logger.warning(f"Budget pressure: {msg}")
                except Exception as e:
                    errors.append(f"Budget pressure [{church_name}]: {e}")
                    logger.error(f"Budget pressure check failed for {church_name}: {e}")

        # 3. Email admin if any issues found across all churches
        if issues:
            body = "TreasuryHealthAgent detected the following issues:\n\n"
            body += "\n".join(f"• {i}" for i in issues)
            body += "\n\nPlease review in the ChurchSaaS admin dashboard."
            try:
                await notifications.send_email(
                    to=ADMIN_EMAIL,
                    subject=f"[Treasury Alert] {len(issues)} issue(s) detected",
                    body=body,
                )
            except Exception as e:
                errors.append(str(e))

        duration_ms = int((time.time() - start) * 1000)
        await log_action(
            agent_name=self.name,
            action="treasury_health_check",
            status="SUCCESS" if not errors else "FAILED",
            output_data={"issues_found": len(issues), "errors": errors},
            triggered_by="SCHEDULED",
            duration_ms=duration_ms,
        )
        logger.info(f"{self.name} done. Issues: {len(issues)}")
        return {"issues": issues, "errors": errors}
