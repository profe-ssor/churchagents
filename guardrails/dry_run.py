"""
dry_run.py — When DRY_RUN=true, log what an agent WOULD do without doing it.
Set in .env: DRY_RUN=true
"""
import os
import logging

logger = logging.getLogger("dry_run")
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"


def maybe_send_email(to: str, subject: str, body: str, send_fn) -> str:
    if DRY_RUN:
        logger.info(f"[DRY RUN] Would send email → {to} | Subject: {subject}")
        return "dry_run_skipped"
    return send_fn(to=to, subject=subject, body=body)


def maybe_write_db(description: str, write_fn, *args, **kwargs):
    if DRY_RUN:
        logger.info(f"[DRY RUN] Would write to DB: {description}")
        return None
    return write_fn(*args, **kwargs)
