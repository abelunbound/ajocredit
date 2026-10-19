"""Sign-up, sign-in, sessions, and refresh tokens.

Access tokens are PyJWT, about 15 minutes, and checked against ``clock.now()``.
Refresh tokens are opaque. Only their SHA-256 hash is stored. Each use rotates
the token. Logout revokes the session, which rejects its access token and
every refresh token that belongs to it.

Sign-up returns the same body whether or not the email is already registered.
Sign-in returns the same error for an unknown email and a wrong password, and
runs a bcrypt check on both paths.

``enforce_auth_attempt_policy`` rate-limits signup, login, password reset,
and verification resend per IP and per account. Login, reset, and resend also
lock the account for longer after repeated attempts. Windows and lock expiry
use ``clock.now()``. The client IP is ``request.client.host`` only.
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import threading
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field, TypeAdapter, ValidationError
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import audit_email
import mail
from clock import now as clock_now
from database import (
    AuthAccountGuard,
    AuthAuditEvent,
    AuthRateBucket,
    AuthSession,
    RefreshToken,
    SessionLocal,
    User,
    get_db,
)

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 15
REFRESH_TOKEN_DAYS = 14
# PyJWT would compare iat and nbf with the wall clock. We compare them with
# clock.now() instead, and allow this much skew.
ACCESS_CLOCK_LEEWAY = timedelta(seconds=10)
BCRYPT_MAX_BYTES = 72
MIN_PASSWORD_CHARS = 8

SIGNUP_DETAIL = "If this email can be registered, the account is ready. Sign in to continue."
LOGIN_FAILED = "Invalid email or password."
REFRESH_FAILED = "Invalid or expired refresh token."
TOKEN_FAILED = "Invalid or expired token."
RATE_LIMITED = "Too many attempts. Try again later."
AUDIT_UNAVAILABLE = "Audit logging is not configured."

_email_adapter = TypeAdapter(EmailStr)
_bearer = HTTPBearer()
# Synthetic addresses used in dev and tests. email-validator rejects the
# reserved .test TLD, so this domain is checked locally and never looked up.
_EXAMPLE_TEST_DOMAIN = "example.test"
_LOCAL_PART = re.compile(r"^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+$")
_dummy_lock = threading.Lock()
_dummy_password_hash: bytes | None = None


def _bounded_int(name: str, default: int, low: int, high: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    if value < low or value > high:
        return default
    return value


def access_token_minutes() -> int:
    """Minutes an access token stays valid. Capped at one hour.

    A 30-day JWT is not accepted. ``JWT_EXPIRY_DAYS`` is ignored.
    """
    return _bounded_int("ACCESS_TOKEN_MINUTES", ACCESS_TOKEN_MINUTES, 1, 60)


def refresh_token_days() -> int:
    """Lifetime of one refresh token. Rotation issues a new one."""
    return _bounded_int("REFRESH_TOKEN_DAYS", REFRESH_TOKEN_DAYS, 1, 30)


def _example_test_email(cleaned: str) -> str | None:
    """Accept ``name@example.test`` without a DNS lookup. Other domains return None."""
    if cleaned.count("@") != 1:
        return None
    local, domain = cleaned.split("@")
    if domain != _EXAMPLE_TEST_DOMAIN and not domain.endswith("." + _EXAMPLE_TEST_DOMAIN):
        return None
    if (
        not local
        or local.startswith(".")
        or local.endswith(".")
        or ".." in local
        or not _LOCAL_PART.fullmatch(local)
    ):
        raise ValueError("Enter an email address.")
    return cleaned


def normalise_email(value: object) -> str:
    """Trim and lowercase, then check the address. Uniqueness uses this form."""
    if not isinstance(value, str):
        raise ValueError("Enter an email address.")
    cleaned = value.strip().lower()
    if not cleaned or len(cleaned) > 320 or any(char.isspace() for char in cleaned):
        raise ValueError("Enter an email address.")
    synthetic = _example_test_email(cleaned)
    if synthetic is not None:
        return synthetic
    try:
        validated = str(_email_adapter.validate_python(cleaned)).strip().lower()
    except ValidationError as exc:
        raise ValueError("Enter an email address.") from exc
    return validated


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def dummy_password_hash() -> bytes:
    """A real bcrypt hash used when no account exists, so login cost matches."""
    global _dummy_password_hash
    if _dummy_password_hash is None:
        with _dummy_lock:
            if _dummy_password_hash is None:
                _dummy_password_hash = bcrypt.hashpw(
                    b"not-a-registered-user",
                    bcrypt.gensalt(),
                )
    return _dummy_password_hash


def password_matches(password: str, hashed: str | bytes) -> bool:
    try:
        material = hashed.encode("utf-8") if isinstance(hashed, str) else hashed
        return bcrypt.checkpw(password.encode("utf-8"), material)
    except (ValueError, TypeError):
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


AUTH_ATTEMPT_ACTIONS = frozenset({"signup", "login", "password_reset", "resend_verification"})
LOCKOUT_ACTIONS = frozenset({"login", "password_reset", "resend_verification"})
# Messages, not password guesses. The account cap allows this many to be sent.
EMAIL_ACTIONS = frozenset({"password_reset", "resend_verification"})
ATTEMPT_WINDOW = timedelta(minutes=15)
QUIET_PERIOD = timedelta(hours=24)
DEV_ENVS = frozenset({"local", "dev"})
# Production caps for one 15-minute window. An unset AJO_ENV uses these.
# Login's per-account cap sits above the first lockout step; the lockout is
# what stops a password guess. Reset and resend stay at 5 so one address
# cannot be mailed in a loop.
STRICT_IP_LIMITS = {
    "signup": 20,
    "login": 50,
    "password_reset": 20,
    "resend_verification": 20,
}
STRICT_ACCOUNT_LIMITS = {
    "signup": 5,
    "login": 20,
    "password_reset": 5,
    "resend_verification": 5,
}
# Higher caps for a laptop or the test suite. Used only when AJO_ENV is
# local or dev. Tests may lower these maps. They are not the production policy.
IP_LIMITS = {
    "signup": 10000,
    "login": 10000,
    "password_reset": 10000,
    "resend_verification": 10000,
}
ACCOUNT_LIMITS = {
    "signup": 100,
    "login": 100,
    "password_reset": 100,
    "resend_verification": 100,
}
# Failure counts that start a lock. Further multiples of the first step stay
# at the longest duration. A successful login, reset, or confirmation clears
# the matching guard.
LOCKOUT_THRESHOLDS = (5, 10, 20)
LOCKOUT_DURATIONS = (
    timedelta(minutes=1),
    timedelta(minutes=15),
    timedelta(hours=1),
)
_LOCKOUT_NOTICE = {
    "login": (
        "Ajo sign-in locked",
        "Sign-in for this account is locked after too many attempts. "
        "You can try again later. If this was not you, reset your password.\n",
    ),
    "password_reset": (
        "Ajo password reset locked",
        "Password reset for this account is locked after too many requests. "
        "You can try again later.\n",
    ),
    "resend_verification": (
        "Ajo verification email locked",
        "Verification email for this account is locked after too many requests. "
        "You can try again later.\n",
    ),
}


def client_host(request: Request) -> str:
    """Client address from the connection. ``X-Forwarded-For`` is not read."""
    if request.client is None or not request.client.host:
        return "unknown"
    return request.client.host[:64]


def _app_env(source: Mapping[str, str] | None = None) -> str:
    env = os.environ if source is None else source
    return str(env.get("AJO_ENV") or "").strip().lower()


def limits_relaxed(source: Mapping[str, str] | None = None) -> bool:
    """True only for a local or dev process. Unset ``AJO_ENV`` is strict."""
    return _app_env(source) in DEV_ENVS


def attempt_limits(
    source: Mapping[str, str] | None = None,
) -> tuple[dict[str, int], dict[str, int]]:
    """Per-IP caps, then per-account caps, for the current environment."""
    if limits_relaxed(source):
        return IP_LIMITS, ACCOUNT_LIMITS
    return STRICT_IP_LIMITS, STRICT_ACCOUNT_LIMITS


def _bucket_scope(kind: str, source: Mapping[str, str] | None = None) -> str:
    """Keep a laptop's counters off the production window.

    ``kind`` is ``ip`` or ``account``. Local and dev add a ``-dev`` suffix.
    The column is 16 characters; both names fit.
    """
    if limits_relaxed(source):
        return f"{kind}-dev"
    return kind


def _email_subject(email: str) -> str:
    try:
        return audit_email.hash_audit_email(email)
    except audit_email.AuditKeyError as exc:
        raise HTTPException(status_code=503, detail=AUDIT_UNAVAILABLE) from exc


def _lock_duration(failures: int) -> timedelta | None:
    if not LOCKOUT_THRESHOLDS or failures < LOCKOUT_THRESHOLDS[0]:
        return None
    if failures in LOCKOUT_THRESHOLDS:
        index = LOCKOUT_THRESHOLDS.index(failures)
    elif failures > LOCKOUT_THRESHOLDS[-1] and (failures % LOCKOUT_THRESHOLDS[0] == 0):
        index = len(LOCKOUT_DURATIONS) - 1
    else:
        return None
    return LOCKOUT_DURATIONS[min(index, len(LOCKOUT_DURATIONS) - 1)]


def _window_open(started: datetime, now: datetime) -> bool:
    return as_utc(started) + ATTEMPT_WINDOW > now


def _bucket(db: Session, *, action: str, scope: str, subject: str, now: datetime) -> AuthRateBucket:
    row = (
        db.query(AuthRateBucket)
        .filter_by(action=action, scope=scope, subject=subject)
        .one_or_none()
    )
    if row is None:
        row = AuthRateBucket(
            action=action,
            scope=scope,
            subject=subject,
            window_started=now,
            attempts=0,
        )
        try:
            with db.begin_nested():
                db.add(row)
                db.flush()
        except IntegrityError:
            row = (
                db.query(AuthRateBucket)
                .filter_by(action=action, scope=scope, subject=subject)
                .one()
            )
    if not _window_open(row.window_started, now):
        row.window_started = now
        row.attempts = 0
    return row


def _guard(db: Session, *, action: str, subject: str, now: datetime) -> AuthAccountGuard:
    row = db.query(AuthAccountGuard).filter_by(action=action, subject=subject).one_or_none()
    if row is None:
        row = AuthAccountGuard(
            action=action,
            subject=subject,
            failures=0,
            level=0,
            locked_until=None,
            last_attempt_at=now,
            notified_level=0,
        )
        try:
            with db.begin_nested():
                db.add(row)
                db.flush()
        except IntegrityError:
            row = db.query(AuthAccountGuard).filter_by(action=action, subject=subject).one()
    if as_utc(row.last_attempt_at) + QUIET_PERIOD <= now and (
        row.locked_until is None or as_utc(row.locked_until) <= now
    ):
        row.failures = 0
        row.level = 0
        row.locked_until = None
        row.notified_level = 0
    return row


def _notify_lockout(
    db: Session,
    *,
    action: str,
    email: str,
    email_hash: str,
    request: Request,
    now: datetime,
) -> None:
    user = db.query(User).filter(User.email == email).one_or_none()
    db.add(
        AuthAuditEvent(
            created_at=now,
            action=f"{action}_lockout",
            user_id=user.id if user is not None else None,
            email_hash=email_hash,
            ip=client_host(request),
        )
    )
    if user is None or not mail.sender_available():
        return
    subject, body = _LOCKOUT_NOTICE[action]
    try:
        mail.send_message(recipient=email, subject=subject, body=body)
    except mail.EmailNotConfigured:
        return


def _email_lock_cuts_allowance(action: str, failures: int, account_cap: int) -> bool:
    """True when a lock would refuse an email the account cap still allows.

    The first lock step and the account cap are both 5. Locking on that count
    would send only 4 messages. A lower lock step, set below the cap, still locks.
    """
    if action not in EMAIL_ACTIONS or not LOCKOUT_THRESHOLDS:
        return False
    return LOCKOUT_THRESHOLDS[0] >= account_cap and failures <= account_cap


def _bump_guard(
    db: Session,
    request: Request,
    *,
    action: str,
    email: str,
    email_hash: str,
    now: datetime,
    account_cap: int | None = None,
) -> bool:
    """Count one failed attempt. Return True when this failure starts a lock."""
    guard = _guard(db, action=action, subject=email_hash, now=now)
    if guard.locked_until is not None and as_utc(guard.locked_until) > now:
        return True
    guard.failures += 1
    guard.last_attempt_at = now
    duration = _lock_duration(guard.failures)
    if duration is None:
        return False
    if account_cap is not None and _email_lock_cuts_allowance(action, guard.failures, account_cap):
        return False
    guard.level += 1
    guard.locked_until = now + duration
    if guard.notified_level != guard.level:
        _notify_lockout(
            db,
            action=action,
            email=email,
            email_hash=email_hash,
            request=request,
            now=now,
        )
        guard.notified_level = guard.level
    return True


def _apply_attempt_policy(
    db: Session, request: Request, *, action: str, email: str, account: bool = True
) -> bool:
    """Record one attempt. Return True when the request must be refused.

    Login failures are counted by ``record_auth_failure`` after the password
    check, so a correct password is not treated as a failure. Reset and
    resend count here because each request is the attempt.

    ``account=False`` is the valid reset-token path. It keeps the per-IP
    limit and skips the per-account limit and the lockout, so a stranger's
    forgot-password requests cannot block the link.
    """
    now = clock_now()
    email_hash = _email_subject(email) if account else ""
    guard = None
    if account and action in LOCKOUT_ACTIONS:
        guard = _guard(db, action=action, subject=email_hash, now=now)
        if guard.locked_until is not None and as_utc(guard.locked_until) > now:
            return True

    ip_caps, account_caps = attempt_limits()
    ip_bucket = _bucket(
        db, action=action, scope=_bucket_scope("ip"), subject=client_host(request), now=now
    )
    account_bucket = None
    if account:
        account_bucket = _bucket(
            db, action=action, scope=_bucket_scope("account"), subject=email_hash, now=now
        )
    over_account = account_bucket is not None and account_bucket.attempts >= account_caps[action]
    if ip_bucket.attempts >= ip_caps[action] or over_account:
        return True

    ip_bucket.attempts += 1
    if account_bucket is not None:
        account_bucket.attempts += 1
    if not account or guard is None or action == "login":
        return False
    return _bump_guard(
        db,
        request,
        action=action,
        email=email,
        email_hash=email_hash,
        now=now,
        account_cap=account_caps[action],
    )


def enforce_auth_attempt_policy(
    request: Request, *, action: str, email: str, account: bool = True
) -> None:
    """Rate-limit one auth attempt and lock the account when the streak says so.

    Signup, login, password reset, and resend-verification call this after the
    email is normalised. ``action`` is one of those four names. ``email`` is
    the normalised address. The stored subject is its HMAC, not the address.
    The client IP is ``request.client.host`` when present. ``X-Forwarded-For``
    is not read.

    Pass ``account=False`` for a valid password-reset token. That request
    still counts against the IP cap and does not count against the account
    cap or the lockout.

    A refused attempt raises ``HTTPException(status_code=429)`` with the same
    detail for every action and every address. This is the only limiter on
    these routes.
    """
    if action not in AUTH_ATTEMPT_ACTIONS:
        raise ValueError(f"unknown auth action: {action}")
    if not email:
        raise ValueError("email is required")
    db = SessionLocal()
    try:
        blocked = _apply_attempt_policy(
            db, request, action=action, email=email, account=account
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    if blocked:
        raise HTTPException(status_code=429, detail=RATE_LIMITED)


def record_auth_failure(request: Request, *, action: str, email: str) -> None:
    """Count a failed login. Raise 429 when this failure starts a lock.

    Known and unknown addresses share this path. The stored subject is the
    email HMAC. A correct password does not call this.
    """
    if action not in LOCKOUT_ACTIONS:
        raise ValueError(f"unknown auth action: {action}")
    if not email:
        raise ValueError("email is required")
    now = clock_now()
    email_hash = _email_subject(email)
    db = SessionLocal()
    try:
        locked = _bump_guard(
            db, request, action=action, email=email, email_hash=email_hash, now=now
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    if locked:
        raise HTTPException(status_code=429, detail=RATE_LIMITED)


def clear_auth_failure_state(db: Session, action: str, email: str) -> None:
    """Forget the lockout streak after a successful login, reset, or confirmation.

    The per-IP window is left as it is. A missing audit key does not block the
    success path.
    """
    if action not in LOCKOUT_ACTIONS:
        return
    try:
        email_hash = audit_email.hash_audit_email(email)
    except audit_email.AuditKeyError:
        return
    db.query(AuthAccountGuard).filter_by(action=action, subject=email_hash).delete()
    db.query(AuthRateBucket).filter(
        AuthRateBucket.action == action,
        AuthRateBucket.scope.in_(("account", "account-dev")),
        AuthRateBucket.subject == email_hash,
    ).delete(synchronize_session=False)


def _password_problem(password: str) -> str | None:
    if len(password) < MIN_PASSWORD_CHARS:
        return f"Password must be at least {MIN_PASSWORD_CHARS} characters."
    if len(password.encode("utf-8")) > BCRYPT_MAX_BYTES:
        return "Password must be at most 72 bytes."
    return None


def _reject_password(password: str) -> None:
    problem = _password_problem(password)
    if problem:
        raise HTTPException(status_code=422, detail=problem)


class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: str
    password: str

    def normalised_email(self) -> str:
        try:
            return normalise_email(self.email)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


class SignupResponse(BaseModel):
    detail: str


class LoginRequest(BaseModel):
    email: str
    password: str

    def normalised_email(self) -> str:
        try:
            return normalise_email(self.email)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=512)


class AuthTokens(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class SessionView(BaseModel):
    id: int
    created_at: datetime
    expires_at: datetime
    current: bool


class SessionList(BaseModel):
    sessions: list[SessionView]


def create_access_token(user_id: int, session_id: int, *, secret: str) -> str:
    moment = clock_now()
    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "typ": "access",
        "iat": int(moment.timestamp()),
        "exp": int((moment + timedelta(minutes=access_token_minutes())).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def _claim_time(payload: dict, name: str) -> datetime:
    return datetime.fromtimestamp(int(payload[name]), tz=timezone.utc)


def _decode_access_token(token: str, *, secret: str, allow_expired: bool = False) -> dict:
    """Check the signature, then exp, iat, and nbf against ``clock.now()``.

    PyJWT's own time checks stay off. They use the wall clock, so a test clock
    that has moved forward would reject every newly issued token.
    """
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
            options={
                "verify_exp": False,
                "verify_iat": False,
                "verify_nbf": False,
                "require": ["exp", "iat", "sub", "sid", "typ"],
            },
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=TOKEN_FAILED) from exc
    if payload.get("typ") != "access":
        raise HTTPException(status_code=401, detail=TOKEN_FAILED)
    try:
        expires = _claim_time(payload, "exp")
        issued = _claim_time(payload, "iat")
        not_before = _claim_time(payload, "nbf") if payload.get("nbf") is not None else None
    except (TypeError, ValueError, OverflowError, OSError, KeyError) as exc:
        raise HTTPException(status_code=401, detail=TOKEN_FAILED) from exc
    now = clock_now()
    leeway = ACCESS_CLOCK_LEEWAY
    if issued > now + leeway:
        raise HTTPException(status_code=401, detail=TOKEN_FAILED)
    if not_before is not None and not_before > now + leeway:
        raise HTTPException(status_code=401, detail=TOKEN_FAILED)
    if not allow_expired and now >= expires + leeway:
        raise HTTPException(status_code=401, detail=TOKEN_FAILED)
    return payload


def _active_session(db: Session, session_id: int) -> AuthSession:
    row = db.get(AuthSession, session_id)
    if row is None or row.revoked_at is not None or as_utc(row.expires_at) <= clock_now():
        raise HTTPException(status_code=401, detail=TOKEN_FAILED)
    return row


def reject_password(password: str) -> None:
    """Raise 422 when a password is outside the bcrypt length rules."""
    _reject_password(password)


def revoke_all_sessions(db: Session, user_id: int, when: datetime | None = None) -> None:
    """End every live session for this account, including refresh tokens."""
    moment = when or clock_now()
    rows = (
        db.query(AuthSession)
        .filter(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .all()
    )
    for row in rows:
        revoke_session(db, row, moment)


def revoke_session(db: Session, row: AuthSession, when: datetime | None = None) -> None:
    """End a session and every refresh token that belongs to it."""
    moment = when or clock_now()
    if row.revoked_at is None:
        row.revoked_at = moment
    db.query(RefreshToken).filter(
        RefreshToken.session_id == row.id,
        RefreshToken.revoked_at.is_(None),
    ).update({RefreshToken.revoked_at: moment}, synchronize_session=False)


def _consume_refresh_token(db: Session, token_hash: str, when: datetime):
    """Mark one live refresh token revoked. Returns the row only when exactly one matched.

    The token is consumed by this UPDATE. Callers must not read the row and
    then set ``revoked_at`` afterwards.
    """
    result = db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > when,
        )
        .values(revoked_at=when)
        .returning(RefreshToken.id, RefreshToken.session_id)
    )
    rows = result.all()
    if len(rows) != 1:
        return None
    return rows[0]


def _revoke_reused_refresh_family(db: Session, token_hash: str, when: datetime) -> None:
    """A token that was already rotated ends the whole session."""
    row = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash, RefreshToken.revoked_at.is_not(None))
        .one_or_none()
    )
    if row is None:
        db.rollback()
        return
    session_row = db.get(AuthSession, row.session_id)
    if session_row is not None:
        revoke_session(db, session_row, when)
    db.commit()


def _issue_refresh(db: Session, session_row: AuthSession, *, when: datetime) -> str:
    raw = secrets.token_urlsafe(32)
    expires = when + timedelta(days=refresh_token_days())
    db.add(
        RefreshToken(
            session_id=session_row.id,
            token_hash=hash_token(raw),
            created_at=when,
            expires_at=expires,
        )
    )
    session_row.expires_at = expires
    return raw


def start_session(db: Session, user: User, *, secret: str) -> AuthTokens:
    when = clock_now()
    row = AuthSession(
        user_id=user.id,
        created_at=when,
        expires_at=when,
    )
    db.add(row)
    db.flush()
    raw_refresh = _issue_refresh(db, row, when=when)
    db.commit()
    return AuthTokens(
        access_token=create_access_token(user.id, row.id, secret=secret),
        refresh_token=raw_refresh,
        expires_in=access_token_minutes() * 60,
    )


def _login_failed() -> HTTPException:
    return HTTPException(status_code=401, detail=LOGIN_FAILED)


def register_auth_routes(fastapi_app: FastAPI, *, jwt_secret: str):
    """Mount sign-up, login, refresh, logout, and session routes.

    Returns the dependency that resolves the signed-in user from an access token.
    """

    def current_user(
        credentials: HTTPAuthorizationCredentials = Depends(_bearer),
        db: Session = Depends(get_db),
    ) -> User:
        payload = _decode_access_token(credentials.credentials, secret=jwt_secret)
        try:
            user_id = int(payload["sub"])
            session_id = int(payload["sid"])
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=401, detail=TOKEN_FAILED) from exc
        _active_session(db, session_id)
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=401, detail=TOKEN_FAILED)
        return user

    @fastapi_app.post("/api/v1/auth/signup", response_model=SignupResponse, status_code=201)
    def signup(body: SignupRequest, request: Request, db: Session = Depends(get_db)):
        email = body.normalised_email()
        enforce_auth_attempt_policy(request, action="signup", email=email)
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="Enter a name.")
        _reject_password(body.password)
        from email_verification import require_sender, send_signup_notice

        require_sender()
        # Hash on every attempt so an existing email is not cheaper to probe.
        hashed_password = hash_password(body.password)
        existing = db.query(User).filter(User.email == email).one_or_none()
        created = False
        user = existing
        if existing is None:
            user = User(name=name, email=email, hashed_password=hashed_password)
            db.add(user)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                user = db.query(User).filter(User.email == email).one_or_none()
            else:
                created = True
        try:
            send_signup_notice(db, user=user, email=email, created=created)
        except HTTPException:
            db.rollback()
            raise
        db.commit()
        return SignupResponse(detail=SIGNUP_DETAIL)

    @fastapi_app.post("/api/v1/auth/login", response_model=AuthTokens)
    def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
        email = body.normalised_email()
        limited: HTTPException | None = None
        try:
            enforce_auth_attempt_policy(request, action="login", email=email)
        except HTTPException as exc:
            if exc.status_code != 429:
                raise
            limited = exc
        # A locked or rate-limited attempt still runs bcrypt, so a known
        # address and an unknown one take the same time and return the same
        # 429. The password result is not used once the attempt is refused.
        _reject_password(body.password)
        user = db.query(User).filter(User.email == email).one_or_none()
        if user is None:
            password_matches(body.password, dummy_password_hash())
        elif not password_matches(body.password, user.hashed_password):
            user = None
        if limited is not None:
            raise limited
        if user is None:
            # Release the read before the failure row is written on its own session.
            db.rollback()
            record_auth_failure(request, action="login", email=email)
            raise _login_failed()
        clear_auth_failure_state(db, "login", email)
        return start_session(db, user, secret=jwt_secret)

    @fastapi_app.post("/api/v1/auth/refresh", response_model=AuthTokens)
    def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
        when = clock_now()
        token_hash = hash_token(body.refresh_token)
        consumed = _consume_refresh_token(db, token_hash, when)
        if consumed is None:
            _revoke_reused_refresh_family(db, token_hash, when)
            raise HTTPException(status_code=401, detail=REFRESH_FAILED)
        token_id, session_id = int(consumed.id), int(consumed.session_id)
        session_row = db.get(AuthSession, session_id)
        user = db.get(User, session_row.user_id) if session_row is not None else None
        if (
            session_row is None
            or user is None
            or session_row.revoked_at is not None
            or as_utc(session_row.expires_at) <= when
        ):
            db.commit()
            raise HTTPException(status_code=401, detail=REFRESH_FAILED)
        raw_refresh = _issue_refresh(db, session_row, when=when)
        db.flush()
        successor = (
            db.query(RefreshToken)
            .filter(RefreshToken.token_hash == hash_token(raw_refresh))
            .one()
        )
        linked = db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.id == token_id,
                RefreshToken.replaced_by_id.is_(None),
            )
            .values(replaced_by_id=successor.id)
        )
        if linked.rowcount != 1:
            db.rollback()
            raise HTTPException(status_code=401, detail=REFRESH_FAILED)
        db.commit()
        return AuthTokens(
            access_token=create_access_token(user.id, session_row.id, secret=jwt_secret),
            refresh_token=raw_refresh,
            expires_in=access_token_minutes() * 60,
        )

    @fastapi_app.post("/api/v1/auth/logout", status_code=204)
    def logout(
        credentials: HTTPAuthorizationCredentials = Depends(_bearer),
        db: Session = Depends(get_db),
    ):
        payload = _decode_access_token(
            credentials.credentials, secret=jwt_secret, allow_expired=True
        )
        try:
            session_id = int(payload["sid"])
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=401, detail=TOKEN_FAILED) from exc
        row = db.get(AuthSession, session_id)
        if row is None:
            raise HTTPException(status_code=401, detail=TOKEN_FAILED)
        revoke_session(db, row)
        db.commit()
        return None

    @fastapi_app.get("/api/v1/auth/sessions", response_model=SessionList)
    def list_sessions(
        credentials: HTTPAuthorizationCredentials = Depends(_bearer),
        db: Session = Depends(get_db),
    ):
        payload = _decode_access_token(credentials.credentials, secret=jwt_secret)
        try:
            user_id = int(payload["sub"])
            session_id = int(payload["sid"])
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=401, detail=TOKEN_FAILED) from exc
        _active_session(db, session_id)
        when = clock_now()
        rows = (
            db.query(AuthSession)
            .filter(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .order_by(AuthSession.id)
            .all()
        )
        visible = [row for row in rows if as_utc(row.expires_at) > when]
        return SessionList(
            sessions=[
                SessionView(
                    id=row.id,
                    created_at=as_utc(row.created_at),
                    expires_at=as_utc(row.expires_at),
                    current=row.id == session_id,
                )
                for row in visible
            ]
        )

    @fastapi_app.delete("/api/v1/auth/sessions/{session_id}", status_code=204)
    def delete_session(
        session_id: int,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ):
        row = db.get(AuthSession, session_id)
        if row is None or row.user_id != user.id:
            raise HTTPException(status_code=404, detail="Session not found.")
        revoke_session(db, row)
        db.commit()
        return None

    return current_user
