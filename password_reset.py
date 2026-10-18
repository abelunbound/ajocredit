"""Forgot-password links. The HTTP response does not reveal whether the email exists.

The link is single-use, expires 30 minutes after ``clock.now()``, and only its
SHA-256 hash is stored. The presented token is consumed by one conditional
update. A successful reset re-hashes the password, ends every session and
refresh token, and uses up any other open reset links. Audit rows store
HMAC-SHA256 of the email, never the address itself.

Forgot-password requests call ``enforce_auth_attempt_policy``, which
rate-limits by email HMAC and IP and can lock further requests. A valid
reset token still counts against the IP limit and skips the per-account
limit and the lockout. Audit rows record the request and the completed
reset, and never store the token, the link, or the password.
"""

from __future__ import annotations

import os
import secrets
from datetime import timedelta

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlalchemy.orm import Session

import audit_email
import mail
from auth import (
    clear_auth_failure_state,
    enforce_auth_attempt_policy,
    hash_password,
    hash_token,
    normalise_email,
    reject_password,
    revoke_all_sessions,
)
from clock import now as clock_now
from database import AuthAuditEvent, PasswordResetToken, User, get_db

RESET_TOKEN_MINUTES = 30
FORGOT_DETAIL = "If an account exists for that email, a reset link is on its way."
RESET_OK = "Your password has been reset. Sign in again."
RESET_INVALID = "This reset link is invalid or has expired."
EMAIL_UNAVAILABLE = "Email cannot be sent until a mail provider is configured."
AUDIT_UNAVAILABLE = "Audit logging is not configured."


class ForgotPasswordRequest(BaseModel):
    email: str


class ForgotPasswordResponse(BaseModel):
    detail: str


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)
    password: str


class ResetPasswordResponse(BaseModel):
    detail: str


def _client_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    host = request.client.host
    return host[:64] if host else None


def _require_audit_key() -> None:
    try:
        audit_email.audit_email_key()
    except audit_email.AuditKeyError as exc:
        raise HTTPException(status_code=503, detail=AUDIT_UNAVAILABLE) from exc


def _audit(db: Session, *, action: str, user_id: int | None, email: str, request: Request) -> None:
    db.add(
        AuthAuditEvent(
            created_at=clock_now(),
            action=action,
            user_id=user_id,
            email_hash=audit_email.hash_audit_email(email),
            ip=_client_ip(request),
        )
    )


def reset_link(token: str) -> str:
    base = os.getenv("PUBLIC_APP_URL", "http://127.0.0.1:8000").rstrip("/")
    return f"{base}/reset-password#{token}"


def _require_sender() -> None:
    if mail.sender_available():
        return
    raise HTTPException(status_code=503, detail=EMAIL_UNAVAILABLE)


def register_password_reset_routes(fastapi_app: FastAPI) -> None:
    @fastapi_app.post("/api/v1/auth/password/forgot", response_model=ForgotPasswordResponse)
    def forgot_password(body: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
        try:
            email = normalise_email(body.email)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        enforce_auth_attempt_policy(request, action="password_reset", email=email)
        _require_sender()
        _require_audit_key()
        user = db.query(User).filter(User.email == email).one_or_none()
        raw = secrets.token_urlsafe(32)
        if user is not None:
            when = clock_now()
            db.add(
                PasswordResetToken(
                    user_id=user.id,
                    token_hash=hash_token(raw),
                    created_at=when,
                    expires_at=when + timedelta(minutes=RESET_TOKEN_MINUTES),
                )
            )
            try:
                mail.send_message(
                    recipient=email,
                    subject="Reset your Ajo password",
                    body=(
                        "Use this link within 30 minutes to choose a new password.\n"
                        f"{reset_link(raw)}\n"
                        "If you did not ask for this, you can ignore this message.\n"
                    ),
                )
            except mail.EmailNotConfigured as exc:
                db.rollback()
                raise HTTPException(status_code=503, detail=EMAIL_UNAVAILABLE) from exc
        _audit(
            db,
            action="password_reset_requested",
            user_id=user.id if user is not None else None,
            email=email,
            request=request,
        )
        db.commit()
        return ForgotPasswordResponse(detail=FORGOT_DETAIL)

    @fastapi_app.post("/api/v1/auth/password/reset", response_model=ResetPasswordResponse)
    def reset_password(body: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
        reject_password(body.password)
        _require_audit_key()
        hashed = hash_password(body.password)
        when = clock_now()
        token_hash = hash_token(body.token)
        matched = (
            db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > when,
            )
            .one_or_none()
        )
        if matched is None:
            raise HTTPException(status_code=400, detail=RESET_INVALID)
        user = db.get(User, int(matched.user_id))
        if user is None:
            raise HTTPException(status_code=400, detail=RESET_INVALID)
        email = user.email
        # End the read transaction before the limiter opens its own session.
        # A valid token skips the per-account cap and the lockout. The per-IP
        # cap still applies, so forgot-password requests cannot block the link.
        db.rollback()
        enforce_auth_attempt_policy(
            request, action="password_reset", email=email, account=False
        )
        when = clock_now()
        consumed = db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > when,
            )
            .values(used_at=when)
            .returning(PasswordResetToken.user_id)
        ).all()
        if len(consumed) != 1:
            db.rollback()
            raise HTTPException(status_code=400, detail=RESET_INVALID)
        user = db.get(User, int(consumed[0].user_id))
        if user is None:
            db.rollback()
            raise HTTPException(status_code=400, detail=RESET_INVALID)
        user.hashed_password = hashed
        revoke_all_sessions(db, user.id, when)
        db.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
            )
            .values(used_at=when)
        )
        _audit(
            db,
            action="password_reset_completed",
            user_id=user.id,
            email=user.email,
            request=request,
        )
        clear_auth_failure_state(db, "password_reset", user.email)
        db.commit()
        return ResetPasswordResponse(detail=RESET_OK)
