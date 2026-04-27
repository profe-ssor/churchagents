"""
Email copy variants for MemberCareAgent / orchestrator member flows.

Keep tone pastoral and configurable — bodies are plain text for notifications.send_email.
"""


def birthday_body(first_name: str, church_name: str) -> str:
    return (
        f"Dear {first_name},\n\n"
        f"Happy Birthday! We celebrate you today at {church_name}.\n\n"
        f"May this year bring you joy, peace, and God's blessings.\n\n"
        f"With love,\n{church_name}"
    )


def visitor_followup_body(
    visitor_first: str,
    church_name: str,
    days_since_visit: int,
    *,
    variant: str = "generic",
) -> str:
    """variant: 'd3' | 'd7' | 'generic' — D+3 / D+7 tone from lifecycle spec."""
    name = visitor_first or "Friend"
    if variant == "d3":
        return (
            f"Dear {name},\n\n"
            f"It was wonderful to meet you at {church_name} a few days ago.\n\n"
            f"Here's more about what we offer — worship times, small groups, and how to plug in.\n\n"
            f"We'd love to see you again.\n\n"
            f"God bless,\n{church_name}"
        )
    if variant == "d7":
        return (
            f"Dear {name},\n\n"
            f"We'd love to have you join our church family at {church_name}. "
            f"You visited about {days_since_visit} days ago — there's a place for you here.\n\n"
            f"Reply to this email or stop by this Sunday.\n\n"
            f"Warmly,\n{church_name}"
        )
    return (
        f"Dear {name},\n\n"
        f"Thank you for visiting {church_name} {days_since_visit} days ago.\n\n"
        f"We would love to see you again. Our doors are always open.\n\n"
        f"God bless you,\n{church_name}"
    )


def welcome_body(first_name: str, church_name: str) -> str:
    return (
        f"Dear {first_name},\n\n"
        f"Welcome to {church_name}! We're glad you're part of the family.\n\n"
        f"Here's how to get started: join us for worship, connect with a small group, "
        f"and reach out if you have questions.\n\n"
        f"Blessings,\n{church_name}"
    )


def inactive_checkin_body(first_name: str, church_name: str) -> str:
    return (
        f"Dear {first_name},\n\n"
        f"We miss you at {church_name}! It's been a while since we've seen you.\n\n"
        f"Come back and reconnect — we'd love to hear how you're doing.\n\n"
        f"In Christ,\n{church_name}"
    )
