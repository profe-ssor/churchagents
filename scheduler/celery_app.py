"""
celery_app.py — Celery app + Beat schedule for all agents.
Run worker: celery -A scheduler.celery_app worker --beat -Q agents,celery --loglevel=info
"""
import os
from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

load_dotenv()

app = Celery(
    "churchagents",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
    include=["scheduler.tasks"],
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Africa/Accra",   # Change to your timezone
    enable_utc=True,
    task_routes={
        "scheduler.tasks.run_subscription_watchdog": {"queue": "agents"},
        "scheduler.tasks.run_treasury_health": {"queue": "agents"},
        "scheduler.tasks.run_member_care": {"queue": "agents"},
        "scheduler.tasks.run_member_care_inactive_scan": {"queue": "agents"},
        "scheduler.tasks.run_audit_security": {"queue": "agents"},
        "scheduler.tasks.run_announcement": {"queue": "agents"},
        "scheduler.tasks.run_department_program": {"queue": "agents"},
        "scheduler.tasks.run_secretariat": {"queue": "agents"},
        "scheduler.tasks.run_orchestrator_daily_briefing": {"queue": "agents"},
    },
)

app.conf.beat_schedule = {
    # Subscription: every 6 hours
    "subscription-watchdog": {
        "task": "scheduler.tasks.run_subscription_watchdog",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    # Treasury: every 12 hours
    "treasury-health": {
        "task": "scheduler.tasks.run_treasury_health",
        "schedule": crontab(minute=0, hour="*/12"),
    },
    # Member care: daily at 8am
    "member-care": {
        "task": "scheduler.tasks.run_member_care",
        "schedule": crontab(minute=0, hour=8),
    },
    # Member care inactive-only (optional — pair with MEMBER_CARE_SPLIT_INACTIVE_TO_SUNDAY): Sundays 18:00
    "member-care-inactive-sunday": {
        "task": "scheduler.tasks.run_member_care_inactive_scan",
        "schedule": crontab(minute=0, hour=18, day_of_week=6),
    },
    # Audit / security: nightly full scan (1:00 AM server time)
    "audit-security": {
        "task": "scheduler.tasks.run_audit_security",
        "schedule": crontab(minute=0, hour=1),
    },
    # Announcements: daily at 9am
    "announcement": {
        "task": "scheduler.tasks.run_announcement",
        "schedule": crontab(minute=0, hour=9),
    },
    # Departments: every 12 hours
    "department-program": {
        "task": "scheduler.tasks.run_department_program",
        "schedule": crontab(minute=0, hour="*/12"),
    },
    # Secretariat: daily at 7am
    "secretariat": {
        "task": "scheduler.tasks.run_secretariat",
        "schedule": crontab(minute=0, hour=7),
    },
    # Orchestrator: platform daily briefing (emails if PLATFORM_BRIEFING_EMAILS is set)
    "orchestrator-daily-briefing": {
        "task": "scheduler.tasks.run_orchestrator_daily_briefing",
        "schedule": crontab(minute=0, hour=7),
    },
}
