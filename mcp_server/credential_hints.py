"""
User-facing guidance when agents cannot reach Django or lack required scope.

Used by orchestrator responses and logs — keep wording actionable, no secrets.
"""

DJANGO_AGENT_AUTH_HELP = (
    "Integration auth failed. To load live church data, set these in churchagents `.env` "
    "to match a real user on your Django API: "
    "`DJANGO_BASE_URL` (e.g. http://localhost:8000), "
    "`AGENT_JWT_EMAIL`, `AGENT_JWT_PASSWORD`. "
    "If that email belongs to multiple churches, or you use a platform administrator "
    "account for agents, set `AGENT_JWT_CHURCH_ID` to the church UUID — it is sent as "
    "`X-Church-ID` on API requests so outbound email/SMS logs attach to that tenant. "
    "Restart agents after changing `.env`. "
    "Verify login with POST `/api/auth/login/` on `DJANGO_BASE_URL` using the same email and password."
)

MEMBER_STATS_NEED_CHURCH_ID = (
    "This question needs per-church member data. Provide the church UUID as `church_id` "
    "(e.g. POST to orchestrator `/ask` with "
    '`{"question":"...","session_id":"...","church_id":"<uuid>"}`). '
    "You can copy the UUID from Django admin or from GET `/api/auth/churches/` "
    "when authenticated. The interactive CLI `python main.py orchestrator` does not "
    "send `church_id` unless you add it."
)

OPENAI_API_KEY_MISSING = (
    "Set `OPENAI_API_KEY` in churchagents `.env` (see `.env.example`), then restart."
)


def auth_configuration_message() -> str:
    """Short paragraph for prompts / answers when Django JWT login or API auth fails."""
    return DJANGO_AGENT_AUTH_HELP


def looks_like_auth_or_scope_error(exc: BaseException) -> bool:
    s = str(exc).lower()
    needles = (
        "django login",
        "invalid email",
        "401",
        "unauthorized",
        "403",
        "forbidden",
        "not authenticated",
        "could not validate credentials",
        "authentication credentials",
        "jwt",
        "token",
        "permission denied",
        "missing church context",
    )
    return any(n in s for n in needles)
