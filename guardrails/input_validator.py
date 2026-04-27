"""
input_validator.py — Sanitise all inputs before they reach an LLM or MCP tool.
"""
import re
from pydantic import BaseModel, field_validator

MAX_QUESTION_LENGTH = 1000

INJECTION_PHRASES = [
    "ignore previous", "system:", "you are now", "jailbreak",
    "disregard all", "forget your instructions",
]


class AdminQuestion(BaseModel):
    question: str
    session_id: str

    @field_validator("question")
    @classmethod
    def clean(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Question cannot be empty")
        if len(v) > MAX_QUESTION_LENGTH:
            raise ValueError(f"Question too long (max {MAX_QUESTION_LENGTH} chars)")
        v = re.sub(r"<[^>]+>", "", v)   # strip HTML tags
        lower = v.lower()
        for phrase in INJECTION_PHRASES:
            if phrase in lower:
                raise ValueError("Suspicious input blocked")
        return v


def validate_church_id(church_id) -> int:
    try:
        cid = int(church_id)
        if cid <= 0:
            raise ValueError
        return cid
    except (TypeError, ValueError):
        raise ValueError(f"Invalid church_id: {church_id}")


def validate_email_payload(payload: dict) -> dict:
    """Ensure email tool calls have required fields before sending."""
    required = {"to", "subject", "body"}
    missing = required - payload.keys()
    if missing:
        raise ValueError(f"Email payload missing fields: {missing}")
    to = (payload.get("to") or "").strip()
    if not to:
        raise ValueError("Email recipient address is empty — skipping send")
    if not re.match(r"[^@]+@[^@]+\.[^@]+", to):
        raise ValueError(f"Invalid email address: {to}")
    return payload
