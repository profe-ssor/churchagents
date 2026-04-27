"""
AuditSecurityAgent (AGENT 7)
- Scans Django AuditLog via /api/activity/ (failed logins, RBAC, deletes, odd-hour logins)
- Lockouts via /api/auth/users/?locked_only=true
- Optional treasury cross-check when church context exists
- Creates AgentAlert rows and optional admin email on critical findings
"""
import os
import time
import logging
from datetime import datetime, timezone

from dotenv import load_dotenv
from monitoring.langsmith_setup import configure
from guardrails.rate_limiter import check_rate_limit
from mcp_server.tools import audit_security as audit_tools
from mcp_server.tools import notifications, treasury as treasury_mcp
from mcp_server.tools.agent_infra import log_action, create_alert

load_dotenv()
configure()
logger = logging.getLogger("audit_security")
AGENT_NAME = "AuditSecurityAgent"
ADMIN_EMAIL = os.getenv("PLATFORM_ADMIN_EMAIL", "").strip()
FAILED_LOGIN_THRESHOLD = 5


class AuditSecurityAgent:
    def __init__(self):
        self.name = AGENT_NAME

    async def run(self):
        start = time.time()
        check_rate_limit(self.name)
        results: dict = {
            "suspicious_events": 0,
            "bulk_flags": 0,
            "lockout_alerts": 0,
            "errors": [],
        }

        try:
            bulk = await audit_tools.detect_bulk_actions(
                church_id=None, threshold=10, window_minutes=5
            )
            if bulk.get("bulk_flag"):
                results["bulk_flags"] += 1
                results["suspicious_events"] += 1
                await create_alert(
                    agent_name=self.name,
                    alert_type="BULK",
                    message=(
                        f"Mass delete signal: {bulk.get('delete_events_in_window')} DELETE events "
                        f"in {bulk.get('window_minutes')}m (threshold {bulk.get('threshold')})."
                    ),
                    severity="WARNING",
                )

            failed_summary = await audit_tools.get_failed_login_attempts(
                threshold=FAILED_LOGIN_THRESHOLD, church_id=None
            )
            flagged = failed_summary.get("flagged_brute_force_candidates") or {}
            for key, count in flagged.items():
                results["suspicious_events"] += 1
                await create_alert(
                    agent_name=self.name,
                    alert_type="LOGIN",
                    message=f"Brute-force pattern: {count} failed logins for {key}",
                    severity="CRITICAL",
                )

            locked = await audit_tools.get_locked_accounts(church_id=None)
            for u in locked[:20]:
                if not isinstance(u, dict):
                    continue
                results["lockout_alerts"] += 1
                results["suspicious_events"] += 1
                await create_alert(
                    agent_name=self.name,
                    alert_type="LOCKOUT",
                    message=(
                        f"Account locked: {u.get('email') or u.get('username')} "
                        f"(failed attempts: {u.get('failed_login_attempts')})"
                    ),
                    severity="CRITICAL",
                    church_id=str(u.get("church") or "") or None,
                )

            unusual = await audit_tools.check_unusual_login_hours(church_id=None)
            if unusual.get("flagged_count", 0) > 0:
                results["suspicious_events"] += 1
                await create_alert(
                    agent_name=self.name,
                    alert_type="LOGIN",
                    message=(
                        f"Unusual-hour logins (UTC): {unusual.get('flagged_count')} in sample week "
                        f"(hours {unusual.get('odd_hours_utc')})."
                    ),
                    severity="WARNING",
                )

            perm = await audit_tools.get_permission_changes(church_id=None, range_token="week")
            resp = perm.get("response")
            rows = resp.get("results", []) if isinstance(resp, dict) else []
            if len(rows) > 0:
                await create_alert(
                    agent_name=self.name,
                    alert_type="PERM",
                    message=(
                        f"RBAC audit: {len(rows)} permission/role change rows in the last week "
                        f"(see /api/activity/?actions=PERMISSION_CHANGE,ROLE_CHANGE)."
                    ),
                    severity="WARNING",
                )
                results["suspicious_events"] += 1

            # Treasury cross-reference: sample churches with treasury-related model activity
            church_ids: set[str] = set()
            for entry in rows:
                if not isinstance(entry, dict):
                    continue
                mn = (entry.get("model_name") or "").lower()
                if any(x in mn for x in ("income", "expense", "transaction", "budget")):
                    cid = entry.get("church")
                    if cid:
                        church_ids.add(str(cid))
            for cid in list(church_ids)[:5]:
                try:
                    large = await treasury_mcp.get_large_transactions(
                        church_id=cid, threshold=5000
                    )
                    if isinstance(large, list) and len(large) >= 3:
                        await create_alert(
                            agent_name=self.name,
                            alert_type="TREASURY_CROSSREF",
                            message=(
                                f"TreasuryHealthAgent cross-check: {len(large)} large transactions "
                                f"for church {cid} while audit showed financial-model activity."
                            ),
                            severity="WARNING",
                            church_id=cid,
                        )
                        results["suspicious_events"] += 1
                except Exception as te:
                    logger.debug("treasury cross-ref skip %s: %s", cid, te)

            if results["suspicious_events"] and ADMIN_EMAIL:
                try:
                    await notifications.send_email(
                        to=ADMIN_EMAIL,
                        subject="[AuditSecurityAgent] Scheduled scan findings",
                        body=(
                            f"UTC {datetime.now(timezone.utc).isoformat()}\n"
                            f"Suspicious signals: {results['suspicious_events']}\n"
                            f"Bulk flags: {results['bulk_flags']}, Lockout alerts: {results['lockout_alerts']}\n"
                            "Review AgentAlert rows in the dashboard."
                        ),
                    )
                except Exception as mail_exc:
                    logger.warning("Audit digest email failed: %s", mail_exc)

        except Exception as e:
            results["errors"].append(str(e))
            logger.error(f"Audit check failed: {e}")

        duration_ms = int((time.time() - start) * 1000)
        await log_action(
            agent_name=self.name,
            action="audit_security_scan",
            status="SUCCESS" if not results["errors"] else "FAILED",
            output_data=results,
            triggered_by="SCHEDULED",
            duration_ms=duration_ms,
        )
        return results
