"""
tasks.py — Celery tasks that wrap each agent's async run() method.
asyncio.run() is used because Celery workers are synchronous by default.
"""
import asyncio
import logging
from scheduler.celery_app import app

logger = logging.getLogger("scheduler")


@app.task(name="scheduler.tasks.run_subscription_watchdog", bind=True, max_retries=2)
def run_subscription_watchdog(self):
    try:
        from agents.subscription_watchdog import SubscriptionWatchdogAgent
        return asyncio.run(SubscriptionWatchdogAgent().run())
    except Exception as exc:
        logger.error(f"SubscriptionWatchdog failed: {exc}")
        raise self.retry(exc=exc, countdown=60)


@app.task(name="scheduler.tasks.run_treasury_health", bind=True, max_retries=2)
def run_treasury_health(self):
    try:
        from agents.treasury_health import TreasuryHealthAgent
        return asyncio.run(TreasuryHealthAgent().run())
    except Exception as exc:
        logger.error(f"TreasuryHealth failed: {exc}")
        raise self.retry(exc=exc, countdown=60)


@app.task(name="scheduler.tasks.run_member_care", bind=True, max_retries=2)
def run_member_care(self):
    try:
        from agents.member_care import MemberCareAgent
        return asyncio.run(MemberCareAgent().run())
    except Exception as exc:
        logger.error(f"MemberCare failed: {exc}")
        raise self.retry(exc=exc, countdown=60)


@app.task(name="scheduler.tasks.run_member_care_inactive_scan", bind=True, max_retries=2)
def run_member_care_inactive_scan(self):
    """Optional Sunday-beat: inactive digest + optional check-in emails (see MemberCareAgent)."""
    try:
        from agents.member_care import MemberCareAgent
        return asyncio.run(MemberCareAgent().run_inactive_scan_only())
    except Exception as exc:
        logger.error(f"MemberCare inactive scan failed: {exc}")
        raise self.retry(exc=exc, countdown=60)


@app.task(name="scheduler.tasks.run_audit_security", bind=True, max_retries=2)
def run_audit_security(self):
    try:
        from agents.audit_security import AuditSecurityAgent
        return asyncio.run(AuditSecurityAgent().run())
    except Exception as exc:
        logger.error(f"AuditSecurity failed: {exc}")
        raise self.retry(exc=exc, countdown=60)


@app.task(name="scheduler.tasks.run_announcement", bind=True, max_retries=2)
def run_announcement(self):
    try:
        from agents.announcement import AnnouncementAgent
        return asyncio.run(AnnouncementAgent().run())
    except Exception as exc:
        logger.error(f"Announcement failed: {exc}")
        raise self.retry(exc=exc, countdown=60)


@app.task(name="scheduler.tasks.run_department_program", bind=True, max_retries=2)
def run_department_program(self):
    try:
        from agents.department_program import DepartmentProgramAgent
        return asyncio.run(DepartmentProgramAgent().run())
    except Exception as exc:
        logger.error(f"DepartmentProgram failed: {exc}")
        raise self.retry(exc=exc, countdown=60)


@app.task(name="scheduler.tasks.run_secretariat", bind=True, max_retries=2)
def run_secretariat(self):
    try:
        from agents.secretariat_agent import SecretariatAgent
        return asyncio.run(SecretariatAgent().run())
    except Exception as exc:
        logger.error(f"Secretariat failed: {exc}")
        raise self.retry(exc=exc, countdown=60)


@app.task(name="scheduler.tasks.run_orchestrator_daily_briefing", bind=True, max_retries=2)
def run_orchestrator_daily_briefing(self):
    try:
        from agents.orchestrator import OrchestratorAgent
        return asyncio.run(OrchestratorAgent().run_scheduled_daily_briefing())
    except Exception as exc:
        logger.error(f"Orchestrator daily briefing failed: {exc}")
        raise self.retry(exc=exc, countdown=120)
