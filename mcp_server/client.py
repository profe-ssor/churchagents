"""
client.py — Base async HTTP client for all MCP tool calls to Django.
"""
import json
import os
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from mcp_server.auth import auth_headers

BASE_URL = os.getenv("DJANGO_BASE_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = 20


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return isinstance(exc, (httpx.ConnectError, httpx.TimeoutException))


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
    reraise=True,
)
async def get(path: str, params: dict = None) -> dict | list:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
        resp = await client.get(path, params=params, headers=auth_headers())
        resp.raise_for_status()
        return resp.json()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
    reraise=True,
)
async def post(
    path: str, data: dict, extra_headers: dict | None = None
) -> dict:
    headers = dict(auth_headers())
    if extra_headers:
        headers.update(extra_headers)
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
        resp = await client.post(path, json=data, headers=headers)
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = json.dumps(e.response.json(), ensure_ascii=False)[:2000]
            except Exception:
                detail = (e.response.text or "")[:2000]
            raise RuntimeError(
                f"Django API HTTP {e.response.status_code} {path}: {detail}"
            ) from e
        return resp.json()


async def patch(path: str, data: dict) -> dict:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
        resp = await client.patch(path, json=data, headers=auth_headers())
        resp.raise_for_status()
        return resp.json()
