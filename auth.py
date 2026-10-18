"""Sign-up, sign-in, sessions, and refresh tokens.

Access tokens are PyJWT, about 15 minutes, and checked against ``clock.now()``.
Refresh tokens are opaque. Only their SHA-256 hash is stored. Each use rotates
the token. Logout revokes the session, which rejects its access token and
every refresh token that belongs to it.

Sign-up returns the same body whether or not the email is already registered.
Sign-in returns the same error for an unknown email and a wrong password, and
runs a bcrypt check on both paths.

``enforce_auth_attempt_policy`` is the single function #40 should replace to
add rate limits and lockout. Signup and login both call it. It does not limit
anything yet.
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import threading
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field, TypeAdapter, ValidationError
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from clock import now as clock_now
from database import AuthSession, RefreshToken, User, get_db

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


def enforce_auth_attempt_policy(request: Request, *, action: str, email: str) -> None:
    """Plug-in point for #40. Rate limiting and lockout are not implemented.

    Signup and login both call this after the email is normalised and before
    any password work. ``action`` is ``signup`` or ``login``. ``email`` is the
    normalised address. The client IP is ``request.client.host`` when present.
    ``X-Forwarded-For`` is not read.

    #40 should replace this function. Raise ``HTTPException(status_code=429)``
    to refuse an attempt. Do not add a second limiter on the routes.
    """
    if action not in {"signup", "login"}:
        raise ValueError(f"unknown auth action: {action}")
    if not email:
        raise ValueError("email is required")
    del request


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
        # Hash on every attempt so an existing email is not cheaper to probe.
        hashed_password = hash_password(body.password)
        existing = db.query(User).filter(User.email == email).one_or_none()
        if existing is None:
            db.add(User(name=name, email=email, hashed_password=hashed_password))
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
        return SignupResponse(detail=SIGNUP_DETAIL)

    @fastapi_app.post("/api/v1/auth/login", response_model=AuthTokens)
    def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
        email = body.normalised_email()
        enforce_auth_attempt_policy(request, action="login", email=email)
        _reject_password(body.password)
        user = db.query(User).filter(User.email == email).one_or_none()
        if user is None:
            password_matches(body.password, dummy_password_hash())
            raise _login_failed()
        if not password_matches(body.password, user.hashed_password):
            raise _login_failed()
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
