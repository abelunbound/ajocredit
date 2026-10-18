"""SQLAlchemy engine, session, and models shared by SQLite and PostgreSQL.

Local development uses SQLite (``DATABASE_URL=sqlite:///local/ajo.db``). CI and,
later, GCP Cloud SQL use a ``postgresql://`` URL. The models and migrations
stay on portable SQLAlchemy types so the same code runs on both.

Money amounts are integer pence. Ledger tables live in ``ledger.py`` and
share this ``Base`` so one metadata registry covers SQLite and PostgreSQL.
"""

from __future__ import annotations

import os
from collections.abc import Generator

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    event,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


def normalize_database_url(url: str) -> str:
    """Point a plain Postgres URL at the psycopg2 driver this project pins.

    SQLAlchemy 2.1 treats ``postgresql://`` as psycopg 3. ``psycopg2-binary``
    is the installed driver, so rewrite the scheme before creating an engine.
    SQLite URLs are unchanged.
    """
    if url.startswith("postgresql+"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://") :]
    return url


def _database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is required but not set. "
            "Use sqlite:///local/ajo.db for local development."
        )
    return normalize_database_url(url)


def _ensure_sqlite_directory(url: str) -> None:
    """Create the parent directory for a file-backed SQLite database."""
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite":
        return
    database = parsed.database
    if not database or database == ":memory:":
        return
    parent = os.path.dirname(os.path.abspath(database))
    if parent:
        os.makedirs(parent, exist_ok=True)


def _engine_for(url: str) -> Engine:
    _ensure_sqlite_directory(url)
    kwargs: dict = {}
    if make_url(url).get_backend_name() == "sqlite":
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_pre_ping"] = True
    return create_engine(url, **kwargs)


def _enable_sqlite_foreign_keys(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    @event.listens_for(engine, "connect")
    def _set_pragma(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


DATABASE_URL = _database_url()
engine = _engine_for(DATABASE_URL)
_enable_sqlite_foreign_keys(engine)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    """Account created by POST /api/v1/auth/signup.

    ``email`` is stored trimmed and lowercased. Uniqueness is on that form.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuthSession(Base):
    """Server-side sign-in session. Logout and password reset set ``revoked_at``."""

    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RefreshToken(Base):
    """Opaque refresh token. Only the SHA-256 hash is stored."""

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("auth_sessions.id"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("refresh_tokens.id"), nullable=True
    )


class PasswordResetToken(Base):
    """Single-use password reset. Only the SHA-256 hash of the token is stored."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuthAuditEvent(Base):
    """Auth event for #32. No password, token, or reset link is stored."""

    __tablename__ = "auth_audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    email_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AuthRateBucket(Base):
    """Fixed window of auth attempts for one IP or one email HMAC.

    ``subject`` is the client host, or the HMAC of the email. It is never the
    raw address. ``scope`` is ``ip`` or ``account``.
    """

    __tablename__ = "auth_rate_buckets"
    __table_args__ = (
        UniqueConstraint("action", "scope", "subject", name="uq_auth_rate_buckets_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    subject: Mapped[str] = mapped_column(String(64), nullable=False)
    window_started: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)


class AuthAccountGuard(Base):
    """Progressive lockout for one action and one email HMAC.

    ``subject`` is the HMAC of the email, never the address. ``locked_until``
    is compared with ``clock.now()``.
    """

    __tablename__ = "auth_account_guards"
    __table_args__ = (
        UniqueConstraint("action", "subject", name="uq_auth_account_guards_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    subject: Mapped[str] = mapped_column(String(64), nullable=False)
    failures: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notified_level: Mapped[int] = mapped_column(Integer, nullable=False)


class EmailVerificationToken(Base):
    """Single-use email verification. Only the SHA-256 hash of the token is stored."""

    __tablename__ = "email_verification_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Circle(Base):
    """Ajo circle. Creating one requires a verified email."""

    __tablename__ = "circles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CircleMember(Base):
    """Membership in a circle. Joining requires a verified email.

    ``role`` is ``admin`` or ``member`` for this circle only. The database
    default is ``member``. Admin is granted by the server, never by the client.
    """

    __tablename__ = "circle_members"
    __table_args__ = (
        UniqueConstraint("circle_id", "user_id", name="uq_circle_members_circle_user"),
        CheckConstraint("role IN ('admin', 'member')", name="ck_circle_members_role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    circle_id: Mapped[int] = mapped_column(ForeignKey("circles.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(
        String(16), nullable=False, default="member", server_default=text("'member'")
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
