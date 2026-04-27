"""
rate_limiter.py — Token-bucket rate limiter using Redis.
Prevents one agent from hammering the Django API or OpenAI.
"""
import time
import redis
import os

_redis = redis.from_url(os.getenv("AGENT_MEMORY_REDIS_URL", "redis://localhost:6379/2"))

# Max calls per agent per minute — keys must match agent self.name values
RATE_LIMITS = {
    "SubscriptionWatchdogAgent": 30,
    "TreasuryHealthAgent": 20,
    "MemberCareAgent": 30,
    "OrchestratorAgent": 60,
    "DepartmentProgramAgent": 20,
    "AnnouncementAgent": 20,
    "AuditSecurityAgent": 20,
    "SecretariatAgent": 20,
    "default": 20,
}


def check_rate_limit(agent_name: str) -> None:
    """Raises RuntimeError if the agent has exceeded its per-minute call limit."""
    limit = RATE_LIMITS.get(agent_name, RATE_LIMITS["default"])
    key = f"ratelimit:{agent_name}:{int(time.time() // 60)}"
    count = _redis.incr(key)
    if count == 1:
        _redis.expire(key, 90)   # window expires after 1.5 min
    if count > limit:
        raise RuntimeError(
            f"{agent_name} exceeded {limit} calls/min (count={count}). Backing off."
        )
