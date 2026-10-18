"""Prompt shown when a signed-in person still needs to verify their email.

Stub and seeded test users are treated as already verified when the session
does not say otherwise, so the existing screens stay unchanged.
"""

from __future__ import annotations

from flask import session

VERIFY_EMAIL_PROMPT = "Verify your email before creating or joining an Ajo."


def verify_email_banner(verified: bool):
    """Return the prompt, or None when the account is already verified."""
    if verified:
        return None
    from dash import html

    return html.Div(VERIFY_EMAIL_PROMPT, id="verify-email-prompt", className="notice")


def session_email_verified() -> bool:
    """Session flag. Missing means pre-verified (stub and seeded test users)."""
    try:
        value = session.get("email_verified")
    except RuntimeError:
        return True
    if value is None:
        return True
    return bool(value)
