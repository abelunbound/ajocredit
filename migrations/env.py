"""Alembic environment. The database URL always comes from DATABASE_URL.

``render_as_batch`` is on so later ALTERs work on SQLite as well as PostgreSQL.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine.url import make_url

from database import Base, normalize_database_url

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is required to run migrations. "
            "Use sqlite:///local/ajo.db for local development."
        )
    return normalize_database_url(url)


def _engine_kwargs(url: str) -> dict:
    if make_url(url).get_backend_name() == "sqlite":
        return {"connect_args": {"check_same_thread": False}}
    return {}


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _database_url()
    connectable = create_engine(url, poolclass=pool.NullPool, **_engine_kwargs(url))

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
