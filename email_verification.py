"""Email verification. Unverified users can sign in, but cannot create or join an Ajo.

The link is single-use, expires 24 hours after ``clock.now()``, and only its
SHA-256 hash is stored. Sign-up and resend use the dev inbox from ``mail.py``.
The HTTP response does not say whether the email is registered. Audit rows
do not store the token, the link, or the password.
"""

from __future__ import annotations

import os
import secrets
from datetime import timedelta

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import mail
from auth import as_utc, enforce_auth_attempt_policy, hash_token, normalise_email
from clock import now as clock_now
from database import AuthAuditEvent, EmailVerificationToken, User, get_db

VERIFICATION_HOURS = 24
VERIFY_REQUIRED = "Verify your email before creating or joining an Ajo."
RESEND_DETAIL = "If an account needs verification, a new link is on its way."
VERIFIED_DETAIL = "Your email is verified."
VERIFY_INVALID = "This verification link is invalid or has expired."
EMAIL_UNAVAILABLE = "Email cannot be sent until a mail provider is configured."
ALREADY_REGISTERED = (
    "An account for this email already exists. Sign in with your password.\n"
    "If you still need to verify the address, ask for another verification link.\n"
)


class ResendRequest(BaseModel):
    email: str


class MessageResponse(BaseModel):
    detail: str


class ConfirmRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)


def require_sender() -> None:
    if mail.sender_available():
        return
    raise HTTPException(status_code=503, detail=EMAIL_UNAVAILABLE)


def require_verified_email(user: User) -> None:
    """Server-side gate for creating or joining an Ajo."""
    if user.email_verified_at is None:
        raise HTTPException(status_code=403, detail=VERIFY_REQUIRED)


def verification_link(token: str) -> str:
    base = os.getenv("PUBLIC_APP_URL", "http://127.0.0.1:8000").rstrip("/")
    return f"{base}/verify-email#{token}"


def _client_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    host = request.client.host
    return host[:64] if host else None


def _audit(db: Session, *, action: str, user_id: int | None, email: str, request: Request | None) -> None:
    db.add(
        AuthAuditEvent(
            created_at=clock_now(),
            action=action,
            user_id=user_id,
            email_hash=hash_token(email),
            ip=_client_ip(request) if request is not None else None,
        )
    )


def issue_verification_token(db: Session, user: User) -> str:
    """Store a new hashed token and use up any older unused links."""
    when = clock_now()
    raw = secrets.token_urlsafe(32)
    open_links = (
        db.query(EmailVerificationToken)
        .filter(EmailVerificationToken.user_id == user.id, EmailVerificationToken.used_at.is_(None))
        .all()
    )
    for link in open_links:
        link.used_at = when
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            created_at=when,
            expires_at=when + timedelta(hours=VERIFICATION_HOURS),
        )
    )
    return raw


def send_signup_notice(db: Session, *, user: User | None, email: str, created: bool) -> None:
    """Send the signup message. Raises 503 when no sender is allowed."""
    require_sender()
    if created and user is not None:
        raw = issue_verification_token(db, user)
        body = (
            "Confirm your email within 24 hours.\n"
            f"{verification_link(raw)}\n"
            "You can sign in before you confirm, but you cannot create or join an Ajo until you do.\n"
        )
        action = "email_verification_sent"
    else:
        body = ALREADY_REGISTERED
        action = "signup_existing_email"
        raw = ""
    try:
        mail.send_message(recipient=email, subject="Your Ajo account", body=body)
    except mail.EmailNotConfigured as exc:
        raise HTTPException(status_code=503, detail=EMAIL_UNAVAILABLE) from exc
    _audit(
        db,
        action=action,
        user_id=user.id if user is not None else None,
        email=email,
        request=None,
    )
    del raw


def register_email_verification_routes(fastapi_app: FastAPI) -> None:
    @fastapi_app.post("/api/v1/auth/verification/resend", response_model=MessageResponse)
    def resend(body: ResendRequest, request: Request, db: Session = Depends(get_db)):
        try:
            email = normalise_email(body.email)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        enforce_auth_attempt_policy(request, action="resend_verification", email=email)
        require_sender()
        user = db.query(User).filter(User.email == email).one_or_none()
        if user is not None and user.email_verified_at is None:
            raw = issue_verification_token(db, user)
            try:
                mail.send_message(
                    recipient=email,
                    subject="Verify your Ajo email",
                    body=f"Confirm your email within 24 hours.\n{verification_link(raw)}\n",
                )
            except mail.EmailNotConfigured as exc:
                db.rollback()
                raise HTTPException(status_code=503, detail=EMAIL_UNAVAILABLE) from exc
            _audit(db, action="email_verification_sent", user_id=user.id, email=email, request=request)
            db.commit()
        return MessageResponse(detail=RESEND_DETAIL)

    @fastapi_app.post("/api/v1/auth/verification/confirm", response_model=MessageResponse)
    def confirm(body: ConfirmRequest, request: Request, db: Session = Depends(get_db)):
        row = (
            db.query(EmailVerificationToken)
            .filter(EmailVerificationToken.token_hash == hash_token(body.token))
            .one_or_none()
        )
        when = clock_now()
        if row is None or row.used_at is not None or as_utc(row.expires_at) <= when:
            raise HTTPException(status_code=400, detail=VERIFY_INVALID)
        user = db.get(User, row.user_id)
        if user is None:
            raise HTTPException(status_code=400, detail=VERIFY_INVALID)
        row.used_at = when
        if user.email_verified_at is None:
            user.email_verified_at = when
        _audit(db, action="email_verified", user_id=user.id, email=user.email, request=request)
        db.commit()
        return MessageResponse(detail=VERIFIED_DETAIL)
