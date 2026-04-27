"""
auth.py — JWT login to Django backend.
Caches the token in Redis so agents don't login on every call.
"""
import base64
import json
import os
import time
import redis
import httpx
from dotenv import load_dotenv

from mcp_server.credential_hints import DJANGO_AGENT_AUTH_HELP

load_dotenv()

BASE_URL = os.getenv("DJANGO_BASE_URL", "http://localhost:8000").rstrip("/")
# Strip whitespace — trailing space/newline in .env breaks auth silently.
EMAIL = (os.getenv("AGENT_JWT_EMAIL") or "").strip()
PASSWORD = (os.getenv("AGENT_JWT_PASSWORD") or "").strip()


def get_agent_church_id() -> str | None:
    """
    Church UUID for platform-scoped Django calls (X-Church-ID, login church_id).

    Read from the environment on each call so `.env` is respected after load_dotenv
    and optional quotes from editors are stripped.
    """
    raw = (os.getenv("AGENT_JWT_CHURCH_ID") or "").strip()
    if not raw:
        return None
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        raw = raw[1:-1].strip()
    return raw or None

_redis = redis.from_url(os.getenv("AGENT_MEMORY_REDIS_URL", "redis://localhost:6379/2"))
TOKEN_KEY = "agent:jwt:access"
REFRESH_KEY = "agent:jwt:refresh"


def _jwt_expired(access_token: str, skew_seconds: int = 45) -> bool:
    """Return True if JWT exp is missing or past (stdlib only, no crypto verify)."""
    try:
        parts = access_token.split(".")
        if len(parts) != 3:
            return True
        payload_b64 = parts[1]
        pad = (-len(payload_b64)) % 4
        if pad:
            payload_b64 += "=" * pad
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode("ascii")))
        exp = payload.get("exp")
        if exp is None:
            return True
        return time.time() >= float(exp) - skew_seconds
    except Exception:
        return True


def _clear_token_cache() -> None:
    _redis.delete(TOKEN_KEY)
    _redis.delete(REFRESH_KEY)


def _login_failure_message(resp: httpx.Response) -> str:
    """Include Django serializer errors in the message (visible in agent logs)."""
    try:
        body = resp.json()
        if isinstance(body, dict):
            return json.dumps(body, ensure_ascii=False)
    except Exception:
        pass
    text = (resp.text or "").strip()
    return text if text else "(empty body)"


def _extract_login_tokens(data: dict) -> tuple[str, str]:
    """Django login returns {'tokens': {'access', 'refresh'}}; accept flat keys too."""
    inner = data.get("tokens")
    if isinstance(inner, dict) and "access" in inner and "refresh" in inner:
        return inner["access"], inner["refresh"]
    if "access" in data and "refresh" in data:
        return data["access"], data["refresh"]
    raise KeyError("Login response missing access/refresh tokens (expected tokens.access or top-level keys)")


def get_token() -> str:
    """Return a valid JWT access token, refreshing if expired."""
    token = _redis.get(TOKEN_KEY)
    if token:
        access = token.decode()
        if not _jwt_expired(access):
            return access
        _redis.delete(TOKEN_KEY)

    # Try to refresh first
    refresh = _redis.get(REFRESH_KEY)
    if refresh:
        try:
            resp = httpx.post(
                f"{BASE_URL}/api/token/refresh/",
                json={"refresh": refresh.decode()},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                access = data["access"]
                # ROTATE_REFRESH_TOKENS may return a new refresh token.
                new_refresh = data.get("refresh", refresh.decode())
                _cache_tokens(access, new_refresh)
                return access
            if resp.status_code in (401, 403):
                _clear_token_cache()
        except Exception:
            pass

    # Full login
    if not EMAIL or not PASSWORD:
        raise ValueError(
            "Set AGENT_JWT_EMAIL and AGENT_JWT_PASSWORD in .env (matching a Django user)."
        )
    payload = {"email": EMAIL, "password": PASSWORD}
    cid = get_agent_church_id()
    if cid:
        payload["church_id"] = cid

    resp = httpx.post(
        f"{BASE_URL}/api/auth/login/",
        json=payload,
        timeout=10,
    )
    if resp.status_code >= 400:
        raise RuntimeError(
            f"Django login rejected ({resp.status_code}): {_login_failure_message(resp)}\n\n"
            f"{DJANGO_AGENT_AUTH_HELP}"
        )
    access, refresh_token = _extract_login_tokens(resp.json())
    _cache_tokens(access, refresh_token)
    return access


def _cache_tokens(access: str, refresh: str):
    _redis.setex(TOKEN_KEY, 60 * 4, access)       # access expires in 4 min
    _redis.setex(REFRESH_KEY, 60 * 60 * 23, refresh)  # refresh expires in 23h


def auth_headers() -> dict:
    h: dict[str, str] = {"Authorization": f"Bearer {get_token()}"}
    cid = get_agent_church_id()
    if cid:
        h["X-Church-ID"] = cid
    return h
