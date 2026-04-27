"""
output_validator.py — Check agent output before any side-effect (email/DB write).
"""

MAX_EMAIL_BODY_LENGTH = 5000
SUSPICIOUS_PATTERNS = ["<script", "javascript:", "DROP TABLE", "DELETE FROM"]


def validate_email_output(body: str) -> str:
    if len(body) > MAX_EMAIL_BODY_LENGTH:
        raise ValueError("Email body too long — possible runaway LLM output")
    lower = body.lower()
    for pat in SUSPICIOUS_PATTERNS:
        if pat.lower() in lower:
            raise ValueError(f"Suspicious pattern in output: {pat}")
    return body


def validate_agent_action(action: str, allowed_actions: list[str]) -> str:
    if action not in allowed_actions:
        raise ValueError(f"Agent tried disallowed action: {action}")
    return action
