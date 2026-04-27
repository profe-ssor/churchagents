"""
token_tracker.py — Log token usage per agent call to Redis.
Read totals with: python -m monitoring.token_tracker report
"""
import os
import json
import redis
from datetime import date

_redis = redis.from_url(os.getenv("AGENT_MEMORY_REDIS_URL", "redis://localhost:6379/2"))

# Cost per 1M tokens (USD) — update when OpenAI changes pricing
COST_PER_1M = {
    "gpt-4.1":       {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini":  {"input": 0.40, "output": 1.60},
}


def record_usage(agent_name: str, model: str, input_tokens: int, output_tokens: int):
    today = date.today().isoformat()
    key = f"tokens:{today}:{agent_name}"
    _redis.hincrby(key, "input_tokens", input_tokens)
    _redis.hincrby(key, "output_tokens", output_tokens)
    _redis.expire(key, 60 * 60 * 24 * 30)   # keep 30 days

    # Calculate cost
    pricing = COST_PER_1M.get(model, COST_PER_1M["gpt-4.1-mini"])
    cost = (input_tokens / 1_000_000 * pricing["input"]) + \
           (output_tokens / 1_000_000 * pricing["output"])
    _redis.hincrbyfloat(key, "cost_usd", round(cost, 6))


def get_daily_report() -> dict:
    today = date.today().isoformat()
    keys = _redis.keys(f"tokens:{today}:*")
    report = {}
    for key in keys:
        agent = key.decode().split(":")[-1]
        data = _redis.hgetall(key)
        report[agent] = {k.decode(): v.decode() for k, v in data.items()}
    return report


if __name__ == "__main__":
    import json
    print(json.dumps(get_daily_report(), indent=2))
