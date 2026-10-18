"""Seed the two local demo sign-in accounts, and nobody else.

``SEED_DEMO_ACCOUNTS`` must be off in every shared or deployed process. When
it is on and ``AJO_ENV`` is anything other than ``local`` or ``dev``, including
when ``AJO_ENV`` is unset, the process refuses to start. There is no pytest
exception.

The seeded accounts are ``admintest`` and ``membertest``. Their passwords come
from the git-ignored stub credentials file. The ten demo personas stay display
data: this module never reads them and never inserts a user row for them.
"""

from __future__ import annotations

import os
import sys
from typing import Mapping

FLAG_NAME = "SEED_DEMO_ACCOUNTS"
TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
DEV_ENVS = frozenset({"local", "dev"})
DEMO_ACCOUNTS = (
    ("admintest", "admintest@example.test", "Admin Test"),
    ("membertest", "membertest@example.test", "Member Test"),
)


def _source(source: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if source is None else source


def _raw(source: Mapping[str, str], name: str) -> str:
    value = source.get(name)
    if value is None:
        return ""
    return str(value).strip()


def flag_enabled(source: Mapping[str, str] | None = None) -> bool:
    return _raw(_source(source), FLAG_NAME).lower() in TRUE_VALUES


def app_env(source: Mapping[str, str] | None = None) -> str:
    return _raw(_source(source), "AJO_ENV").lower()


def policy_problems(source: Mapping[str, str] | None = None) -> list[str]:
    """Reasons the process must exit because demo seeding is enabled illegally.

    An empty list means startup may continue. The flag being off is always fine.
    ``local`` and ``dev`` are the only environments that may seed. Unset is not.
    """
    if not flag_enabled(source):
        return []
    if app_env(source) in DEV_ENVS:
        return []
    shown = app_env(source) or "(unset)"
    return [
        f"AJO_ENV is {shown!r}; demo accounts can be seeded only when "
        "AJO_ENV is 'local' or 'dev'."
    ]


def _fail(messages: list[str]) -> None:
    for line in messages:
        print(f"ERROR: {line}", file=sys.stderr)
    raise SystemExit(1)


def enforce_demo_seed_policy(source: Mapping[str, str] | None = None) -> None:
    """Abort when demo seeding is enabled outside local or dev.

    A disabled flag does not stop startup and does not read credentials.
    """
    problems = policy_problems(source)
    if not problems:
        return
    _fail(
        [
            "SEED_DEMO_ACCOUNTS is enabled outside local development.",
            "Demo accounts must not be seeded when AJO_ENV is unset or is not local or dev.",
            "Refusing to start.",
            *problems,
        ]
    )


def seed_demo_accounts(source: Mapping[str, str] | None = None) -> None:
    """Insert or refresh ``admintest`` and ``membertest`` when the flag is on.

    Call this only after ``enforce_demo_seed_policy`` and after the database
    engine exists. A flag that is on outside local or dev still refuses to
    start, so a direct call cannot seed a deploy.
    """
    if not flag_enabled(source):
        return
    enforce_demo_seed_policy(source)

    from auth import _password_problem, hash_password
    from database import SessionLocal, User
    from stub_auth import (
        PLACEHOLDER_PASSWORDS,
        StubCredentialsError,
        credentials_path,
        load_stub_passwords,
    )

    path = credentials_path(source)
    try:
        passwords = load_stub_passwords(path)
    except StubCredentialsError as exc:
        _fail([*exc.messages, "Refusing to start."])

    problems: list[str] = []
    usable: dict[str, str] = {}
    for username, _email, _name in DEMO_ACCOUNTS:
        password = passwords.get(username, "")
        if password.strip().lower() in PLACEHOLDER_PASSWORDS:
            problems.append(
                f"Password for {username} is missing or still a placeholder. "
                "Set it in the git-ignored stub credentials file."
            )
            continue
        issue = _password_problem(password)
        if issue:
            problems.append(f"Password for {username} cannot be used: {issue}")
            continue
        usable[username] = password
    if problems:
        _fail(
            [
                "SEED_DEMO_ACCOUNTS is enabled, but demo credentials are not usable.",
                *problems,
                "Refusing to start.",
            ]
        )

    from clock import now as clock_now

    verified_at = clock_now()
    db = SessionLocal()
    try:
        for username, email, name in DEMO_ACCOUNTS:
            hashed = hash_password(usable[username])
            user = db.query(User).filter(User.email == email).one_or_none()
            if user is None:
                user = User(name=name, email=email, hashed_password=hashed)
                db.add(user)
            else:
                user.name = name
                user.hashed_password = hashed
            if user.email_verified_at is None:
                user.email_verified_at = verified_at
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
