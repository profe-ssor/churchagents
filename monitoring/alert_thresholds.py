"""
alert_thresholds.py — Central place for all numeric thresholds.
All agents import from here — never hardcode values in agent files.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _int_list(env_key: str, default: str) -> list[int]:
    return [int(x) for x in os.getenv(env_key, default).split(",")]


# Subscription alerts
SUBSCRIPTION_ALERT_DAYS      = _int_list("SUBSCRIPTION_ALERT_DAYS", "7,3,1")

# Treasury
EXPENSE_STALL_HOURS          = int(os.getenv("EXPENSE_STALL_THRESHOLD_HOURS", "48"))
ANOMALY_AMOUNT               = float(os.getenv("ANOMALY_TRANSACTION_THRESHOLD", "5000"))
BUDGET_UTILIZATION_WARN      = float(os.getenv("TREASURY_BUDGET_UTILIZATION_WARN", "0.80"))
INCOME_STALE_DAYS            = int(os.getenv("TREASURY_INCOME_STALE_DAYS", "14"))

# Members
MEMBER_INACTIVE_DAYS         = int(os.getenv("MEMBER_INACTIVE_DAYS", "30"))
VISITOR_FOLLOWUP_DAYS        = _int_list("VISITOR_FOLLOWUP_DAYS", "3,7")

# Departments / programs
PROGRAM_STALL_HOURS          = int(os.getenv("PROGRAM_STALL_THRESHOLD_HOURS", "72"))

# Token spend guard (triggers a warning log, not a hard stop)
DAILY_TOKEN_SPEND_WARN_USD   = float(os.getenv("DAILY_SPEND_WARN_USD", "2.00"))
DAILY_TOKEN_SPEND_HARD_USD   = float(os.getenv("DAILY_SPEND_HARD_USD", "5.00"))
