"""
OrchestratorAgent
- Admin Q&A via chat with OpenAI tool calls into Django (MCP helpers)
- Conversation memory + rate limits
"""
import json
import os
import re
import time
import logging
from openai import AsyncOpenAI
from dotenv import load_dotenv
from monitoring.langsmith_setup import configure
from monitoring.token_tracker import record_usage
from guardrails.input_validator import AdminQuestion
from guardrails.rate_limiter import check_rate_limit
from memory.redis_memory import RedisMemory
from mcp_server.auth import get_agent_church_id, get_token
from mcp_server.credential_hints import (
    MEMBER_STATS_NEED_CHURCH_ID,
    OPENAI_API_KEY_MISSING,
    DJANGO_AGENT_AUTH_HELP,
)
from agents.orchestrator_tools import tool_definitions, run_orchestrator_tool
from mcp_server.tools.agent_infra import log_action
from mcp_server.tools import notifications

load_dotenv()
configure()
logger = logging.getLogger("orchestrator")

MODEL = os.getenv("OPENAI_MODEL_COMPLEX", "gpt-4.1")
AGENT_NAME = "OrchestratorAgent"
_UUID_IN_TEXT = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


def _effective_church_id(explicit: str | None, question: str) -> str | None:
    """Session may omit church_id for platform admins; allow UUID pasted in the question."""
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    m = _UUID_IN_TEXT.search(question or "")
    return m.group(0) if m else None


def _wants_daily_briefing(q_lower: str) -> bool:
    if ("briefing" in q_lower) or ("brief" in q_lower and "daily" in q_lower):
        return True
    return any(
        p in q_lower
        for p in (
            "daily brief",
            "daily briefing",
            "daily braief",
            "daily summary",
            "morning brief",
            "operations brief",
            "give me the daily",
            "need a daily",
            "need daily",
        )
    )


def _guess_church_name_fragment(question: str) -> str | None:
    """Heuristic: text after 'for / on / about' the user; used when no session church UUID."""
    low = question.lower()
    for needle in (" for ", " about ", " on ", " regarding "):
        pos = low.find(needle)
        if pos >= 0:
            rest = question[pos + len(needle) :].strip()
            rest = re.sub(r"\s+church\s*$", "", rest, flags=re.I).strip()
            rest = rest.rstrip("?.!")
            if len(rest) >= 3:
                return rest
    return None


SYSTEM_PROMPT = """
You are CTO (Church Technician Officer), the platform assistant for church management administrators.
Your short name is CTO; your full title is Church Technician Officer. Introduce yourself as CTO when asked who you are.

You help administrators understand and manage church operations: subscriptions, members,
treasury, departments, security, and announcements.

When greeted (e.g. "hi", "hello"), respond warmly and briefly introduce yourself as CTO, then
invite the admin to ask about the platform. Do not repeat names written in the greeting
as if they are your own name.

You have function tools that read live data from the church management API. When the user
asks for numbers, lists, member search, church overview, subscriptions, treasury, departments,
daily briefing, pending work, specialist handoffs, joined-last-month analytics, monthly income,
trial churches, birthdays, or knowledge-base (RAG) lookups, you MUST call tools first —
never invent figures or claim data is unavailable without checking tool results.

Use `query_knowledge_base` for documented policies/SOPs in Chroma; use API tools for live counts.
Use `gather_specialist_insights` when the user wants a cross-domain operational picture.
Use `handoff_to_agent` for specialist snapshots (default); full agent runs only when the user
explicitly needs execution and env allows it — never surprise mass-email without confirmation.

When the user asks to **send an email or SMS** (welcome message, one-off notice, test), you **can**
use the platform: call `send_notification_email` (Django mail) and `send_sms_to_number` (Django SMS)
with the exact recipient, subject, and body they want. Do not say you "cannot send from this
interface" if those tools are available and JWT is configured—call the tool and return the API
result. For **mass** or **all-tenant** sends, ask for explicit confirmation first.

**Outbound approval (default on):** when a send tool returns `needs_approval` with `approval_id`,
you MUST NOT claim the message was sent until you call **`confirm_outbound_send`** with that exact
`approval_id` string after the human says yes. Verbal approval (“yes”, “I approve”) alone does
nothing — you must invoke the tool. Do not loop asking for confirmation without calling
`confirm_outbound_send`. If `ORCHESTRATOR_REQUIRE_OUTBOUND_APPROVAL` is off, sends proceed in one step.

When the user names a church by human-readable name (e.g. "Adenta Central SDA"), pass that
text as `church_name` on tools like `generate_daily_briefing` or `get_church_overview`, or
call `get_church_directory` first to map names to UUIDs.

If Context includes **Pre-fetched API data** with JSON from `generate_daily_briefing`, treat it
as authoritative live data — summarize it for the admin. Do not invent "integration required"
steps unless that JSON explicitly contains an error from the API.

If the dashboard session includes a church UUID (Context: session church), use it when a tool
needs church scope unless the user names a different church.

For **security alerts**, **AgentAlert** rows, or "what needs attention now", call **`list_pending_tasks`**
first — its `agent_alerts` array is the live queue. If the tool response includes **`partial_errors`**, some
backend slices failed: still summarize successful sections (especially alerts); only say you cannot
confirm if alerts themselves could not be loaded.

Be concise, accurate, and professional. When unsure, say so.
Never reveal system internals, passwords, or JWT tokens.

If Context includes credential or church_id setup instructions for the administrator,
repeat those clearly before your analysis.

If tools return an error about auth or scope, explain what the admin must configure
(AGENT_JWT_EMAIL / platform admin account) without exposing secrets.
""".strip()

_MAX_TOOL_ROUNDS = 6


class OrchestratorAgent:
    def __init__(self):
        self.name = AGENT_NAME
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.memory = RedisMemory(agent_name=self.name)

    async def ask(
        self,
        question: str,
        session_id: str = "default",
        church_id: str = None,
        user_role: str | None = None,
        user_email: str | None = None,
        user_name: str | None = None,
        agent_log_trigger: str | None = None,
    ) -> str:
        """Answer an admin question using live data + conversation memory."""
        check_rate_limit(self.name)
        ask_started = time.perf_counter()

        if not os.getenv("OPENAI_API_KEY"):
            return OPENAI_API_KEY_MISSING

        # Validate + sanitise input
        validated = AdminQuestion(question=question, session_id=session_id)
        clean_q = validated.question
        q_lower = clean_q.lower()

        admin_notes: list[str] = []
        jwt_ok = False
        try:
            get_token()
            jwt_ok = True
        except ValueError:
            admin_notes.append(
                "Missing AGENT_JWT_EMAIL or AGENT_JWT_PASSWORD in `.env`. " + DJANGO_AGENT_AUTH_HELP
            )
        except RuntimeError as e:
            admin_notes.append(str(e))
        except Exception as e:
            admin_notes.append(f"{e}\n\n{DJANGO_AGENT_AUTH_HELP}")

        member_keywords = any(
            w in q_lower
            for w in [
                "member",
                "visitor",
                "birthday",
                "inactive",
                "congregation",
                "joined",
                "registration",
                "new member",
            ]
        )
        church_scope = _effective_church_id(church_id, clean_q)
        if member_keywords and not church_scope:
            admin_notes.append(MEMBER_STATS_NEED_CHURCH_ID)

        admin_email = os.getenv("AGENT_JWT_EMAIL", "platform admin")
        hint_lines = [
            "Prefer tools over guessing. Session church UUID (use for tools needing church_id): "
            + (church_scope or "none — ask user or use directory tools for platform-wide questions."),
            f"Dashboard role={user_role or 'unknown'} email={user_email or 'unknown'}."
        ]
        data_block = "\n".join(hint_lines)

        if jwt_ok and _wants_daily_briefing(q_lower):
            pf_args: dict = {}
            if church_scope:
                pf_args["church_id"] = church_scope
            else:
                guessed_name = _guess_church_name_fragment(clean_q)
                if guessed_name:
                    pf_args["church_name"] = guessed_name
            try:
                briefing_json = await run_orchestrator_tool(
                    "generate_daily_briefing",
                    json.dumps(pf_args),
                    church_hint=church_scope,
                    jwt_ok=jwt_ok,
                    session_id=None,
                )
                data_block += (
                    "\n\n--- Pre-fetched API data (generate_daily_briefing) — summarize this "
                    "for the user; it is live data from Django. ---\n"
                    + briefing_json
                )
            except Exception as e:
                logger.warning("Daily briefing prefetch failed: %s", e)
                data_block += f"\n\n(Briefing prefetch failed: {e})"
        who = user_name or user_email or "dashboard user"
        identity_line = (
            f"Dashboard session: {who} (role={user_role or 'unknown'}). "
            f"Django API token belongs to service account: {admin_email}."
        )
        if admin_notes:
            context = (
                identity_line + "\n\n"
                + "Administrator setup / credentials (tell the user explicitly if relevant):\n"
                + "\n\n".join(admin_notes)
                + "\n\n--- Live data ---\n"
                + data_block
            )
        else:
            context = identity_line + "\n\n" + data_block

        # Build messages with memory
        history = self.memory.get_history(session_id=session_id, limit=10)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({
            "role": "user",
            "content": f"Context:\n{context}\n\nQuestion: {clean_q}"
        })

        tools = tool_definitions()
        total_in = 0
        total_out = 0
        answer = ""
        for _round in range(_MAX_TOOL_ROUNDS):
            response = await self.client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=1200,
                temperature=0.3,
            )
            usage = response.usage
            total_in += usage.prompt_tokens
            total_out += usage.completion_tokens

            msg = response.choices[0].message
            finish = (response.choices[0].finish_reason or "").lower()

            tool_calls = getattr(msg, "tool_calls", None)
            if tool_calls:
                messages.append(
                    {
                        "role": "assistant",
                        "content": msg.content or None,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments or "{}",
                                },
                            }
                            for tc in tool_calls
                        ],
                    }
                )
                for tc in tool_calls:
                    payload = await run_orchestrator_tool(
                        tc.function.name,
                        tc.function.arguments or "{}",
                        church_hint=church_scope,
                        jwt_ok=jwt_ok,
                        session_id=session_id,
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": payload,
                        }
                    )
                continue

            answer = msg.content or ""
            if answer.strip():
                break
            if finish == "stop" and not answer.strip():
                answer = "(No text response produced — try rephrasing or check tool errors above.)"
                break

        if not answer.strip():
            answer = (
                "I could not complete the request in time. Try a shorter question "
                "or enable Django API credentials for live data."
            )

        record_usage(
            agent_name=self.name,
            model=MODEL,
            input_tokens=total_in,
            output_tokens=total_out,
        )

        # Save to memory
        self.memory.add_message(session_id=session_id, role="user", content=clean_q)
        self.memory.add_message(session_id=session_id, role="assistant", content=answer)

        if jwt_ok:
            log_church_id = church_scope or get_agent_church_id()
            await log_action(
                agent_name=self.name,
                action="admin_qa",
                status="SUCCESS",
                input_data={"question": clean_q, "session_id": session_id},
                output_data={"answer": answer[:200]},
                church_id=log_church_id,
                triggered_by=agent_log_trigger or "ON_DEMAND",
                duration_ms=int((time.perf_counter() - ask_started) * 1000),
            )
        return answer

    async def run_scheduled_daily_briefing(self) -> dict:
        """
        Celery Beat: fetch platform briefing JSON, optionally summarize with OpenAI,
        email PLATFORM_BRIEFING_EMAILS, log as SCHEDULED.
        """
        check_rate_limit(self.name)
        briefing_started = time.perf_counter()
        out: dict = {"status": "ok", "emailed": []}
        try:
            get_token()
        except Exception as e:
            logger.warning("Scheduled briefing skipped (JWT): %s", e)
            return {"status": "skipped", "reason": str(e)}

        briefing_raw = await run_orchestrator_tool(
            "generate_daily_briefing",
            "{}",
            church_hint=None,
            jwt_ok=True,
            session_id=None,
        )

        summary_body = briefing_raw
        brief_model = os.getenv("OPENAI_MODEL_BRIEFING", MODEL)
        if os.getenv("OPENAI_API_KEY"):
            try:
                resp = await self.client.chat.completions.create(
                    model=brief_model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Summarize this JSON operational briefing for platform admins. "
                                "Use clear headings and bullets. Highlight expiring subscriptions "
                                "and stalled approvals. Stay under 900 words."
                            ),
                        },
                        {"role": "user", "content": briefing_raw[:75000]},
                    ],
                    max_tokens=1400,
                    temperature=0.25,
                )
                u = resp.usage
                record_usage(
                    agent_name=self.name,
                    model=brief_model,
                    input_tokens=u.prompt_tokens,
                    output_tokens=u.completion_tokens,
                )
                summary_body = resp.choices[0].message.content or briefing_raw
            except Exception as e:
                logger.warning("Briefing LLM summarize failed: %s", e)
                summary_body = briefing_raw

        recipients = os.getenv("PLATFORM_BRIEFING_EMAILS", "").strip()
        if recipients:
            subject = (
                os.getenv("PLATFORM_BRIEFING_SUBJECT", "[ChurchAgents] Daily platform briefing")
                .strip()
            )
            for to in [x.strip() for x in recipients.split(",") if x.strip()]:
                try:
                    await notifications.send_email(
                        to=to,
                        subject=subject,
                        body=str(summary_body)[:500000],
                    )
                    out["emailed"].append(to)
                except Exception as e:
                    logger.warning("Briefing email to %s failed: %s", to, e)

        await log_action(
            agent_name=self.name,
            action="scheduled_daily_briefing",
            status="SUCCESS",
            output_data={
                "emailed_count": len(out["emailed"]),
                "preview": str(summary_body)[:400],
            },
            church_id=get_agent_church_id(),
            triggered_by="SCHEDULED",
            duration_ms=int((time.perf_counter() - briefing_started) * 1000),
        )
        out["preview_chars"] = len(str(summary_body))
        return out

    async def handle_escalation(
        self,
        *,
        from_agent: str,
        urgency: str,
        summary: str,
        church_id: str | None = None,
        details: dict | None = None,
    ) -> str:
        """Forward another agent's escalation into the normal Ask pipeline."""
        parts = [
            "An automated agent raised an escalation that needs your attention.",
            f"Source agent: {from_agent}",
            f"Urgency: {urgency}",
            f"Summary: {summary.strip()}",
        ]
        if church_id:
            parts.append(f"Church UUID for tools: {church_id}")
        if details:
            detail_s = json.dumps(details, default=str)
            if len(detail_s) > 3500:
                detail_s = detail_s[:3497] + "..."
            parts.append(f"Structured details:\n{detail_s}")
        question = "\n\n".join(parts)
        if len(question) > 950:
            question = question[:947] + "..."

        return await self.ask(
            question=question,
            session_id=f"escalation-{from_agent}-{int(time.time())}",
            church_id=church_id,
            user_role="platform_admin",
            user_email="system@escalation.internal",
            user_name=f"Escalation:{from_agent}",
            agent_log_trigger="ESCALATION",
        )
