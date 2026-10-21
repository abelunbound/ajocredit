"""Local demo accounts (#33).

Seeding admintest and membertest is refused unless AJO_ENV is local or dev.
The ten demo personas stay display data: no user rows and no sign-in.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("JWT_SECRET_KEY", "test-only-jwt-secret-key-32chars!!")
os.environ["ALLOW_LOCAL_STUB_LOGIN"] = "false"
os.environ["SEED_DEMO_ACCOUNTS"] = "false"

if "api" not in sys.modules:
    _configured_url = os.environ.get("DATABASE_URL", "")
    if not _configured_url.startswith("postgres"):
        _db_dir = tempfile.mkdtemp(prefix="ajo-demo-")
        os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_db_dir) / "ajo.db")
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")

from fastapi.testclient import TestClient

import api
import database
import demo_accounts
from pages.personas import EXAMPLE_PERSONAS_PATH, load_personas

REPO = Path(__file__).resolve().parents[1]
client = TestClient(api.app)
ADMIN_EMAIL = "admintest@example.test"
MEMBER_EMAIL = "membertest@example.test"
ADMIN_PASSWORD = "local-admin-pass"
MEMBER_PASSWORD = "local-member-pass"


def _run_import(module: str, env: dict):
    child_env = os.environ.copy()
    for name in (
        "ALLOW_TEST_CLOCK",
        "ALLOW_LOCAL_STUB_LOGIN",
        "SEED_DEMO_ACCOUNTS",
        "DASH_HOST",
        "AJO_ENV",
        "PYTEST_CURRENT_TEST",
        "JWT_SECRET_KEY",
        "DATABASE_URL",
        "STUB_USERS_FILE",
    ):
        child_env.pop(name, None)
    child_env["ALLOW_LOCAL_STUB_LOGIN"] = "false"
    child_env["ALLOW_TEST_CLOCK"] = "false"
    child_env.update(env)
    return subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        env=child_env,
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )


def _api_env(**extra):
    env = {
        "JWT_SECRET_KEY": "a" * 32,
        "DATABASE_URL": "sqlite:///:memory:",
        "SEED_DEMO_ACCOUNTS": "true",
    }
    env.update(extra)
    return env


def test_demo_seeding_refuses_to_start_when_ajo_env_is_unset():
    result = _run_import(
        "api",
        _api_env(PYTEST_CURRENT_TEST="tests/test_demo_accounts.py::still-refused"),
    )
    assert result.returncode == 1
    assert "SEED_DEMO_ACCOUNTS is enabled outside local development" in result.stderr
    assert "Refusing to start" in result.stderr
    assert "(unset)" in result.stderr

    dash = _run_import("app_dash_web", {"SEED_DEMO_ACCOUNTS": "true", "AJO_ENV": ""})
    assert dash.returncode == 1
    assert "Refusing to start" in dash.stderr
    assert "(unset)" in dash.stderr


def test_demo_seeding_refuses_to_start_when_ajo_env_is_not_local_or_dev():
    for env_name in ("production", "staging", "test"):
        result = _run_import("api", _api_env(AJO_ENV=env_name))
        assert result.returncode == 1, result.stderr
        assert "Refusing to start" in result.stderr
        assert env_name in result.stderr


def test_demo_seeding_starts_only_for_local_or_dev(tmp_path):
    database_file = tmp_path / "ajo.db"
    credentials = tmp_path / "stub-users.json"
    credentials.write_text(
        json.dumps({"admintest": ADMIN_PASSWORD, "membertest": MEMBER_PASSWORD}),
        encoding="utf-8",
    )
    for env_name in ("local", "dev"):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from alembic import command; from alembic.config import Config; "
                "command.upgrade(Config('alembic.ini'), 'head'); import api",
            ],
            env={
                **os.environ,
                "JWT_SECRET_KEY": "a" * 32,
                "DATABASE_URL": f"sqlite:///{database_file}",
                "SEED_DEMO_ACCOUNTS": "true",
                "AJO_ENV": env_name,
                "ALLOW_LOCAL_STUB_LOGIN": "false",
                "ALLOW_TEST_CLOCK": "false",
                "STUB_USERS_FILE": str(credentials),
                "PYTEST_CURRENT_TEST": "",
            },
            capture_output=True,
            text=True,
            cwd=str(REPO),
        )
        assert result.returncode == 0, result.stderr

    from sqlalchemy import create_engine, text

    engine = create_engine(f"sqlite:///{database_file}")
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT email FROM users ORDER BY email")).all()
        roles = connection.execute(
            text(
                """
                SELECT users.email, circle_members.role
                FROM circle_members
                JOIN users ON users.id = circle_members.user_id
                JOIN circles ON circles.id = circle_members.circle_id
                WHERE circles.name = :name
                ORDER BY users.email
                """
            ),
            {"name": demo_accounts.DEMO_CIRCLE_NAME},
        ).all()
    assert [row[0] for row in rows] == [ADMIN_EMAIL, MEMBER_EMAIL]
    assert [(row[0], row[1]) for row in roles] == [
        (ADMIN_EMAIL, "admin"),
        (MEMBER_EMAIL, "member"),
    ]


def test_demo_personas_have_no_user_rows_and_cannot_sign_in(tmp_path, monkeypatch):
    credentials = tmp_path / "stub-users.json"
    credentials.write_text(
        json.dumps({"admintest": ADMIN_PASSWORD, "membertest": MEMBER_PASSWORD}),
        encoding="utf-8",
    )
    personas = load_personas(EXAMPLE_PERSONAS_PATH)
    assert len(personas["personas"]) == 10
    persona_emails = {persona["email"] for persona in personas["personas"]}
    assert ADMIN_EMAIL not in persona_emails
    assert MEMBER_EMAIL not in persona_emails

    monkeypatch.setenv("SEED_DEMO_ACCOUNTS", "true")
    monkeypatch.setenv("AJO_ENV", "local")
    monkeypatch.setenv("STUB_USERS_FILE", str(credentials))
    demo_accounts.seed_demo_accounts()

    db = database.SessionLocal()
    try:
        stored = {row.email for row in db.query(database.User).all()}
    finally:
        db.close()
    assert ADMIN_EMAIL in stored
    assert MEMBER_EMAIL in stored
    assert persona_emails.isdisjoint(stored)
    db = database.SessionLocal()
    try:
        seeded = db.query(database.User).filter(database.User.email.in_([ADMIN_EMAIL, MEMBER_EMAIL])).all()
        assert len(seeded) == 2
        assert all(row.email_verified_at is not None for row in seeded)
        circle = (
            db.query(database.Circle)
            .filter(database.Circle.name == demo_accounts.DEMO_CIRCLE_NAME)
            .one()
        )
        memberships = (
            db.query(database.CircleMember)
            .filter(database.CircleMember.circle_id == circle.id)
            .all()
        )
        by_email = {row.email: row.id for row in seeded}
        stored_roles = {row.user_id: row.role for row in memberships}
        assert stored_roles[by_email[ADMIN_EMAIL]] == "admin"
        assert stored_roles[by_email[MEMBER_EMAIL]] == "member"
        assert len(stored_roles) == 2
    finally:
        db.close()

    admin = client.post(
        "/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    member = client.post(
        "/api/v1/auth/login",
        json={"email": MEMBER_EMAIL, "password": MEMBER_PASSWORD},
    )
    assert admin.status_code == 200, admin.text
    assert member.status_code == 200, member.text

    for persona in personas["personas"]:
        with_fixture_password = client.post(
            "/api/v1/auth/login",
            json={"email": persona["email"], "password": persona["password"]},
        )
        assert with_fixture_password.status_code != 200
        assert "access_token" not in with_fixture_password.text
        refused = client.post(
            "/api/v1/auth/login",
            json={"email": persona["email"], "password": "not-a-persona-password"},
        )
        assert refused.status_code == 401
        assert refused.json()["detail"] == "Invalid email or password."
