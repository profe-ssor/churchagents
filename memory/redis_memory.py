"""
redis_memory.py — Conversation history stored in Redis per session.
"""
import os
import json
import redis
from dotenv import load_dotenv

load_dotenv()

_redis = redis.from_url(os.getenv("AGENT_MEMORY_REDIS_URL", "redis://localhost:6379/2"))
TTL_SECONDS = 60 * 60 * 24   # 24 hours


class RedisMemory:
    def __init__(self, agent_name: str):
        self.agent_name = agent_name

    def _key(self, session_id: str) -> str:
        return f"memory:{self.agent_name}:{session_id}"

    def add_message(self, session_id: str, role: str, content: str):
        key = self._key(session_id)
        message = json.dumps({"role": role, "content": content})
        _redis.rpush(key, message)
        _redis.expire(key, TTL_SECONDS)

    def get_history(self, session_id: str, limit: int = 20) -> list[dict]:
        key = self._key(session_id)
        raw = _redis.lrange(key, -limit, -1)
        return [json.loads(m) for m in raw]

    def clear(self, session_id: str):
        _redis.delete(self._key(session_id))
