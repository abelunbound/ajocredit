"""Test-only clock (#36).

Tests and a loopback dev control can move time. Production cannot, and a
process that enables the clock outside those cases refuses to start.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import clock
from clock import (
    ClockLocked,
    advance,
    clock_mutable,
    dev_control_allowed,
    enforce_test_clock_policy,
    freeze,
    install_clock,
    now,
    reset,
    restore_for_tests,
)

FROZEN = datetime(2026, 1, 15, 9, 30, tzinfo=timezone.utc)
DEV_SOURCE = {
    "ALLOW_TEST_CLOCK": "true",
    "AJO_ENV": "local",
    "DASH_HOST": "127.0.0.1",
}
PRODUCTION_SOURCE = {
    "ALLOW_TEST_CLOCK": "true",
    "AJO_ENV": "production",
    "DASH_HOST": "127.0.0.1",
    "PYTEST_CURRENT_TEST": "should-not-unlock-production",
}


@pytest.fixture(autouse=True)
def _wall_clock():
    restore_for_tests()
    yield
    restore_for_tests()


def test_now_is_timezone_aware_utc():
    moment = now()
    assert moment.tzinfo is not None
    assert moment.utcoffset() == timedelta(0)


def test_tests_can_freeze_advance_and_reset():
    freeze(FROZEN)
    assert now() == FROZEN
    assert advance(timedelta(days=1, hours=2)) == FROZEN + timedelta(days=1, hours=2)
    reset()
    assert now() != FROZEN
    assert abs((now() - datetime.now(timezone.utc)).total_seconds()) < 5


def test_dev_control_source_can_move_time_without_pytest():
    """A passed-in local loopback env is not the test runner."""
    assert "PYTEST_CURRENT_TEST" not in DEV_SOURCE
    assert dev_control_allowed(DEV_SOURCE)
    assert clock_mutable(DEV_SOURCE)
    freeze(FROZEN, source=DEV_SOURCE)
    assert now(source=DEV_SOURCE) == FROZEN
    assert advance(timedelta(minutes=30), source=DEV_SOURCE) == FROZEN + timedelta(minutes=30)
    reset(source=DEV_SOURCE)


def test_production_cannot_move_or_replace_the_clock():
    freeze(FROZEN)
    assert clock_mutable(PRODUCTION_SOURCE) is False
    assert dev_control_allowed(PRODUCTION_SOURCE) is False
    with pytest.raises(ClockLocked):
        advance(timedelta(seconds=1), source=PRODUCTION_SOURCE)
    with pytest.raises(ClockLocked):
        freeze(FROZEN, source=PRODUCTION_SOURCE)
    with pytest.raises(ClockLocked):
        reset(source=PRODUCTION_SOURCE)
    with pytest.raises(ClockLocked):
        install_clock(clock.Clock(), source=PRODUCTION_SOURCE)

    wall = now(source=PRODUCTION_SOURCE)
    assert wall != FROZEN
    assert abs((wall - datetime.now(timezone.utc)).total_seconds()) < 5
    assert now() == FROZEN


def test_staging_and_a_public_bind_cannot_move_time():
    staging = {"ALLOW_TEST_CLOCK": "true", "AJO_ENV": "staging", "DASH_HOST": "127.0.0.1"}
    public = {"ALLOW_TEST_CLOCK": "true", "AJO_ENV": "local", "DASH_HOST": "0.0.0.0"}
    assert clock_mutable(staging) is False
    assert clock_mutable(public) is False
    with pytest.raises(ClockLocked):
        advance(timedelta(seconds=1), source=staging)
    with pytest.raises(ClockLocked):
        advance(timedelta(seconds=1), source=public)


def test_install_clock_replaces_now_for_tests():
    class Fixed:
        def now(self, source=None):
            return FROZEN

    install_clock(Fixed())
    assert now() == FROZEN
    with pytest.raises(ClockLocked):
        install_clock(Fixed(), source=PRODUCTION_SOURCE)


def test_policy_allows_pytest_and_refuses_a_deploy():
    enforce_test_clock_policy(
        {
            "ALLOW_TEST_CLOCK": "true",
            "AJO_ENV": "test",
            "PYTEST_CURRENT_TEST": "tests/test_clock.py::test_policy (call)",
        }
    )
    enforce_test_clock_policy({"ALLOW_TEST_CLOCK": "false", "AJO_ENV": "production"})
    enforce_test_clock_policy(DEV_SOURCE)

    with pytest.raises(SystemExit):
        enforce_test_clock_policy(PRODUCTION_SOURCE)
    with pytest.raises(SystemExit):
        enforce_test_clock_policy({"ALLOW_TEST_CLOCK": "true", "AJO_ENV": "test"})
    with pytest.raises(SystemExit):
        enforce_test_clock_policy({"ALLOW_TEST_CLOCK": "true", "AJO_ENV": "local", "DASH_HOST": "0.0.0.0"})
    with pytest.raises(SystemExit):
        enforce_test_clock_policy({"ALLOW_TEST_CLOCK": "true"})


def _run_import(module: str, env: dict):
    child_env = os.environ.copy()
    for name in (
        "ALLOW_TEST_CLOCK",
        "ALLOW_LOCAL_STUB_LOGIN",
        "DASH_HOST",
        "AJO_ENV",
        "PYTEST_CURRENT_TEST",
        "JWT_SECRET_KEY",
        "DATABASE_URL",
    ):
        child_env.pop(name, None)
    child_env["ALLOW_LOCAL_STUB_LOGIN"] = "false"
    child_env.update(env)
    return subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        env=child_env,
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )


def _api_env(**extra):
    env = {
        "JWT_SECRET_KEY": "a" * 32,
        "DATABASE_URL": "sqlite:///:memory:",
        "ALLOW_TEST_CLOCK": "false",
    }
    env.update(extra)
    return env


def test_api_refuses_to_start_when_the_clock_is_enabled_outside_tests():
    result = _run_import("api", _api_env(ALLOW_TEST_CLOCK="true", AJO_ENV="production"))
    assert result.returncode == 1
    assert "ALLOW_TEST_CLOCK is enabled outside tests" in result.stderr
    assert "Refusing to start" in result.stderr
    assert "production" in result.stderr

    outside_tests = _run_import("api", _api_env(ALLOW_TEST_CLOCK="true", AJO_ENV="test"))
    assert outside_tests.returncode == 1
    assert "outside tests" in outside_tests.stderr


def test_api_refuses_a_public_dev_bind_and_allows_loopback():
    public = _run_import(
        "api",
        _api_env(ALLOW_TEST_CLOCK="true", AJO_ENV="local", DASH_HOST="0.0.0.0"),
    )
    assert public.returncode == 1
    assert "DASH_HOST" in public.stderr

    local = _run_import(
        "api",
        _api_env(ALLOW_TEST_CLOCK="true", AJO_ENV="local", DASH_HOST="127.0.0.1"),
    )
    assert local.returncode == 0, local.stderr


def test_dash_refuses_a_staging_clock_and_starts_when_the_flag_is_off():
    staging = _run_import(
        "app_dash_web",
        {"ALLOW_TEST_CLOCK": "true", "AJO_ENV": "staging", "DASH_HOST": "127.0.0.1"},
    )
    assert staging.returncode == 1
    assert "outside tests" in staging.stderr
    assert "staging" in staging.stderr

    production = _run_import(
        "app_dash_web",
        {"ALLOW_TEST_CLOCK": "false", "AJO_ENV": "production", "DASH_HOST": "0.0.0.0"},
    )
    assert production.returncode == 0, production.stderr


@pytest.fixture(scope="module")
def api_module():
    saved = {name: os.environ.get(name) for name in ("JWT_SECRET_KEY", "DATABASE_URL", "ALLOW_LOCAL_STUB_LOGIN", "ALLOW_TEST_CLOCK")}
    os.environ.setdefault("JWT_SECRET_KEY", "test-only-jwt-secret-key-32chars!!")
    os.environ["ALLOW_LOCAL_STUB_LOGIN"] = "false"
    os.environ["ALLOW_TEST_CLOCK"] = "false"
    if "api" not in sys.modules and not os.environ.get("DATABASE_URL", "").startswith("postgres"):
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    import api

    yield api

    for name, value in saved.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def test_dev_route_is_absent_unless_the_local_control_is_on(api_module):
    assert not any(getattr(route, "path", None) == "/api/v1/dev/clock" for route in api_module.app.routes)
    client = TestClient(api_module.app)
    assert client.get("/api/v1/dev/clock").status_code == 404

    with pytest.raises(ClockLocked):
        api_module.register_dev_clock_routes(FastAPI())


def test_dev_route_advances_freezes_and_resets(monkeypatch, api_module):
    monkeypatch.setenv("ALLOW_TEST_CLOCK", "true")
    monkeypatch.setenv("AJO_ENV", "local")
    monkeypatch.setenv("DASH_HOST", "localhost")

    app = FastAPI()
    api_module.register_dev_clock_routes(app)
    client = TestClient(app, client=("127.0.0.1", 50000))

    frozen = client.post("/api/v1/dev/clock", json={"freeze_at": "2026-03-01T00:00:00Z"})
    assert frozen.status_code == 200, frozen.text
    assert frozen.json()["now"].startswith("2026-03-01T00:00:00")

    moved = client.post("/api/v1/dev/clock", json={"advance_seconds": 90})
    assert moved.status_code == 200, moved.text
    assert moved.json()["now"].startswith("2026-03-01T00:01:30")
    assert client.get("/api/v1/dev/clock").json()["now"].startswith("2026-03-01T00:01:30")

    both = client.post("/api/v1/dev/clock", json={"advance_seconds": 1, "reset": True})
    assert both.status_code == 422

    cleared = client.post("/api/v1/dev/clock", json={"reset": True})
    assert cleared.status_code == 200
    assert not cleared.json()["now"].startswith("2026-03-01")

    monkeypatch.setenv("AJO_ENV", "production")
    with pytest.raises(ClockLocked):
        api_module.register_dev_clock_routes(FastAPI())


def _dev_clock_app(monkeypatch, api_module):
    monkeypatch.setenv("ALLOW_TEST_CLOCK", "true")
    monkeypatch.setenv("AJO_ENV", "local")
    monkeypatch.setenv("DASH_HOST", "127.0.0.1")
    app = FastAPI()
    api_module.register_dev_clock_routes(app)
    return app


def test_dev_clock_allows_a_loopback_caller(monkeypatch, api_module):
    app = _dev_clock_app(monkeypatch, api_module)
    for host in ("127.0.0.1", "::1"):
        client = TestClient(app, client=(host, 50000))
        response = client.get("/api/v1/dev/clock")
        assert response.status_code == 200, response.text
        assert "now" in response.json()


def test_dev_clock_hides_from_a_non_loopback_caller(monkeypatch, api_module):
    app = _dev_clock_app(monkeypatch, api_module)
    freeze(FROZEN)
    client = TestClient(app, client=("203.0.113.10", 50000))
    assert client.get("/api/v1/dev/clock").status_code == 404
    posted = client.post("/api/v1/dev/clock", json={"advance_seconds": 3600})
    assert posted.status_code == 404
    assert now() == FROZEN


def test_dev_clock_ignores_a_spoofed_forwarded_for(monkeypatch, api_module):
    app = _dev_clock_app(monkeypatch, api_module)
    client = TestClient(app, client=("203.0.113.10", 50000))
    response = client.get(
        "/api/v1/dev/clock",
        headers={
            "X-Forwarded-For": "127.0.0.1",
            "Forwarded": "for=127.0.0.1;proto=http",
        },
    )
    assert response.status_code == 404


def test_signup_token_expiry_follows_the_clock(api_module):
    freeze(FROZEN)
    token = api_module.create_token(7)
    payload = jwt.decode(
        token,
        api_module.JWT_SECRET_KEY,
        algorithms=[api_module.JWT_ALGORITHM],
        options={"verify_exp": False},
    )
    expected = int((FROZEN + timedelta(days=api_module.JWT_EXPIRY_DAYS)).timestamp())
    assert payload["sub"] == "7"
    assert payload["exp"] == expected
