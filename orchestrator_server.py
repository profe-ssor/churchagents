"""
HTTP bridge for OrchestratorAgent (user-facing name: CTO — Church Technician Officer)
— used by church-agents-dashboard via AGENTS_API_URL.

Run (from repo root, with venv + .env loaded):

  pip install fastapi uvicorn
  python orchestrator_server.py

Then in church-agents-dashboard/.env.local:

  AGENTS_API_URL=http://localhost:8001

Internal triggers (Paystack → watchdog, manual briefing, agent escalation):
  POST /internal/trigger/subscription-watchdog
  POST /internal/trigger/daily-briefing
  POST /internal/escalate
  Header: X-ChurchAgents-Internal-Key: <ORCHESTRATOR_INTERNAL_SECRET>

Dashboard (same email as SubscriptionWatchdogAgent / MCP `send_renewal_reminder_email`):
  POST /renewal-reminder
  JSON: { "church_id": "<uuid>", "days_left": 7 }  (days_left 1–365, default 7)

Override port: AGENTS_HTTP_PORT=8002
"""
import asyncio
import logging
import os
import sys
import traceback

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

load_dotenv()

logger = logging.getLogger("orchestrator_server")

app = FastAPI(title="ChurchAgents Orchestrator", version="1.0.0")

if sys.version_info >= (3, 11):
    # Starlette cannot register exception handlers for BaseExceptionGroup (not a subclass of Exception).
    from builtins import BaseExceptionGroup as _BaseExceptionGroup  # noqa: PLC0415
else:

    class _BaseExceptionGroup(Exception):  # type: ignore[misc]
        """Unused placeholder — real BaseExceptionGroup exists only on Python ≥ 3.11."""

        pass


if sys.version_info >= (3, 11):

    @app.middleware("http")
    async def json_on_base_exception_group(request: Request, call_next):
        """Return JSON 500 instead of uvicorn plain-text for 3.11+ task-group failures."""
        try:
            return await call_next(request)
        except _BaseExceptionGroup as eg:
            logger.exception("BaseExceptionGroup in orchestrator")
            inner: BaseException | None = None
            root = eg
            try:
                while isinstance(root, _BaseExceptionGroup) and root.exceptions:
                    sub = root.exceptions[0]
                    if isinstance(sub, _BaseExceptionGroup):
                        root = sub
                        continue
                    inner = sub
                    break
            except Exception:
                inner = None
            label = repr(inner) if inner is not None else repr(eg)
            label_s = label[:800] if isinstance(label, str) else repr(label)[:800]
            payload = {
                "answer": (
                    "Orchestrator raised a grouped exception (often concurrent I/O). "
                    f"Check Redis TLS, Django URL, and OpenAI. Detail: {label_s}"
                ),
                "error": type(eg).__name__,
            }
            return JSONResponse(status_code=500, content=jsonable_encoder(payload))


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    """Always return JSON so Container Apps / proxies never see empty non-JSON 500 bodies."""
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder({"detail": exc.detail, "answer": str(exc.detail)}),
        )
    logger.exception("Unhandled error in orchestrator")
    detail = str(exc).strip() or type(exc).__name__
    logger.debug(traceback.format_exc())
    payload = {
        "answer": (
            f"Orchestrator internal error ({type(exc).__name__}). "
            "Check OPENAI_API_KEY, AGENT_MEMORY_REDIS_URL (TLS), and DJANGO_BASE_URL in the Container App. "
            f"Detail: {detail[:500]}"
        ),
        "error": type(exc).__name__,
    }
    return JSONResponse(status_code=500, content=jsonable_encoder(payload))


def _verify_internal_key(request: Request) -> None:
    expected = os.getenv("ORCHESTRATOR_INTERNAL_SECRET", "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Internal triggers disabled — set ORCHESTRATOR_INTERNAL_SECRET in churchagents .env",
        )
    got = request.headers.get("X-ChurchAgents-Internal-Key") or ""
    if got != expected:
        raise HTTPException(status_code=403, detail="Invalid X-ChurchAgents-Internal-Key")


class AskRequest(BaseModel):
    question: str
    session_id: str = Field(default="default", min_length=1)
    church_id: str | None = None
    user_role: str | None = None
    user_email: str | None = None
    user_name: str | None = None


class EscalateRequest(BaseModel):
    from_agent: str = Field(..., max_length=160)
    urgency: str = Field(default="HIGH", max_length=32)
    summary: str = Field(..., max_length=1200)
    church_id: str | None = None
    details: dict | None = None


class RenewalReminderRequest(BaseModel):
    """Manual renewal reminder — shares template with SubscriptionWatchdogAgent."""

    church_id: str = Field(..., min_length=1)
    days_left: int = Field(default=7, ge=1, le=365)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
async def root() -> dict[str, str]:
    """JSON root so probes and browser hits are not confused with HTML error pages upstream."""
    return {
        "service": "churchagents-orchestrator",
        "health": "/health",
        "ask": "POST /ask",
    }


@app.post("/ask")
async def ask(req: AskRequest) -> dict[str, str]:
    from agents.orchestrator import OrchestratorAgent

    agent = OrchestratorAgent()
    answer = await agent.ask(
        question=req.question,
        session_id=req.session_id,
        church_id=req.church_id,
        user_role=req.user_role,
        user_email=req.user_email,
        user_name=req.user_name,
    )
    return {"answer": answer}


@app.post("/internal/trigger/subscription-watchdog")
async def internal_trigger_subscription_watchdog(request: Request) -> dict:
    """Run SubscriptionWatchdogAgent once (e.g. after Paystack charge.success)."""
    _verify_internal_key(request)
    from agents.subscription_watchdog import SubscriptionWatchdogAgent

    result = await SubscriptionWatchdogAgent().run()
    return {"status": "ok", "result": result}


@app.post("/internal/trigger/daily-briefing")
async def internal_trigger_daily_briefing(request: Request) -> dict:
    """Same work as Celery scheduled daily briefing (email + AgentLog)."""
    _verify_internal_key(request)
    from agents.orchestrator import OrchestratorAgent

    result = await OrchestratorAgent().run_scheduled_daily_briefing()
    return {"status": "ok", "result": result}


@app.post("/renewal-reminder")
async def renewal_reminder(body: RenewalReminderRequest) -> dict:
    """Send one renewal reminder email (same MCP path as the subscription watchdog)."""
    from mcp_server.tools import accounts

    cid = body.church_id.strip()
    result = await accounts.send_renewal_reminder_email(cid, body.days_left)
    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(status_code=400, detail=result)
    return {"status": "ok", "result": result}


@app.post("/internal/escalate")
async def internal_escalate(request: Request, body: EscalateRequest) -> dict[str, str]:
    """Route another agent’s urgent signal through OrchestratorAgent."""
    _verify_internal_key(request)
    from agents.orchestrator import OrchestratorAgent

    answer = await OrchestratorAgent().handle_escalation(
        from_agent=body.from_agent,
        urgency=body.urgency,
        summary=body.summary,
        church_id=body.church_id,
        details=body.details,
    )
    return {"answer": answer}


class _OuterJson500Middleware(BaseHTTPMiddleware):
    """Catches failures Starlette would surface as plain-text ``Internal Server Error`` (e.g. BaseExceptionGroup)."""

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except asyncio.CancelledError:
            raise
        except HTTPException:
            raise
        except RequestValidationError:
            raise
        except BaseException as bexc:
            if isinstance(bexc, asyncio.CancelledError):
                raise
            if sys.version_info >= (3, 11) and isinstance(bexc, _BaseExceptionGroup):
                eg = bexc
                logger.exception("BaseExceptionGroup (outer middleware)")
                label = repr(eg.exceptions[0]) if eg.exceptions else repr(eg)
                return JSONResponse(
                    status_code=500,
                    content=jsonable_encoder(
                        {
                            "answer": f"Orchestrator grouped error. Detail: {label[:700]}",
                            "error": type(eg).__name__,
                        }
                    ),
                )
            if isinstance(bexc, Exception):
                exc = bexc
                logger.exception("Unhandled exception (outer middleware)")
                detail = str(exc).strip() or type(exc).__name__
                return JSONResponse(
                    status_code=500,
                    content=jsonable_encoder(
                        {
                            "answer": (
                                f"Orchestrator error ({type(exc).__name__}). "
                                "Check OPENAI_API_KEY, Redis TLS, DJANGO_BASE_URL. "
                                f"Detail: {detail[:600]}"
                            ),
                            "error": type(exc).__name__,
                        }
                    ),
                )
            raise


# Outermost user middleware (registered last).
app.add_middleware(_OuterJson500Middleware)


def main() -> None:
    import uvicorn

    port = int(os.getenv("AGENTS_HTTP_PORT", "8001"))
    host = os.getenv("AGENTS_HTTP_HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
