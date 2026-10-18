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

from sqlalchemy import DateTime, ForeignKey, Integer, String, create_engine, event
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
