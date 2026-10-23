"""Dash calls the FastAPI app with the server session, not the stub role map.

Tokens stay in the Dash process. The Flask session stores an opaque id.
Only admintest and membertest can sign in. Persona names are refused.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("JWT_SECRET_KEY", "test-only-jwt-secret-key-32chars!!")
os.environ["ALLOW_LOCAL_STUB_LOGIN"] = "false"
os.environ["SEED_DEMO_ACCOUNTS"] = "false"
os.environ.setdefault("AJO_ENV", "local")
os.environ.setdefault("EMAIL_SENDER", "dev")
os.environ.setdefault("AUDIT_EMAIL_HMAC_KEY", "test-only-audit-email-hmac-key")

if "backend.api" not in sys.modules:
    _configured_url = os.environ.get("DATABASE_URL", "")
    if not _configured_url.startswith("postgres"):
        _db_dir = tempfile.mkdtemp(prefix="ajo-dash-api-")
        os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_db_dir) / "ajo.db")
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")

import pytest
from fastapi.testclient import TestClient
from flask import session

import backend.api as api
import backend.clock as clock
import frontend.dash_api as dash_api
import backend.database as database
import backend.demo_accounts as demo_accounts
from frontend.app_dash_web import apply_signin, app, next_state, render_shell
from backend.audit import PLATFORM_ADMIN

ADMIN_PW = "pw-admin"
MEMBER_PW = "pw-member"
http = TestClient(api.app)


def _send(calls):
    def send(method, path, body, headers, params):
        calls.append(
            {
                "method": method,
                "path": path.split("?", 1)[0],
                "body": body,
                "headers": dict(headers),
                "params": params,
            }
        )
        response = http.request(method, path, json=body, headers=headers, params=params)
        payload = response.json() if response.content else None
        return response.status_code, payload

    return send


@pytest.fixture
def api_dash(tmp_path, monkeypatch):
    path = tmp_path / "stub-users.json"
    path.write_text(
        json.dumps({"admintest": ADMIN_PW, "membertest": MEMBER_PW}),
        encoding="utf-8",
    )
    monkeypatch.setenv("STUB_USERS_FILE", str(path))
    monkeypatch.setenv("SEED_DEMO_ACCOUNTS", "true")
    monkeypatch.setenv("AJO_ENV", "local")
    monkeypatch.setenv("ALLOW_LOCAL_STUB_LOGIN", "false")
    monkeypatch.setenv("AJO_API_BASE", "http://127.0.0.1:8000")
    demo_accounts.seed_demo_accounts()
    calls: list[dict] = []
    dash_api.install_transport_for_tests(_send(calls))
    yield calls
    dash_api.install_transport_for_tests(None)
    dash_api.VAULT._rows.clear()
    clock.restore_for_tests()


def _paths(calls, path):
    return [call for call in calls if call["path"] == path]


def test_admintest_signs_in_through_the_api_and_keeps_the_token_off_the_session(api_dash):
    with app.server.test_request_context():
        page, _rev, error = next_state(
            {"type": "auth-btn", "action": "signin-submit"},
            "signin",
            0,
            "admintest",
            ADMIN_PW,
        )
        assert page == "home"
        assert error == ""
        assert session["username"] == "admintest"
        assert session["role"] == "admin"
        assert session["api_sid"]
        assert "access_token" not in session
        assert "refresh_token" not in session
        token = dash_api.VAULT.get(session["api_sid"])["access_token"]
        stored = json.dumps({key: session[key] for key in session})
        assert token not in stored
        assert ADMIN_PW not in stored
        text = str(render_shell("home", "member"))
        assert token not in text
        assert "Local Demo Circle · admin" in text
        assert "PayoutsTracker" in text
    login = _paths(api_dash, "/api/v1/auth/login")
    assert len(login) == 1
    assert login[0]["body"]["email"] == "admintest@example.test"
    assert "role" not in login[0]["body"]
    assert _paths(api_dash, "/api/v1/me")
    assert _paths(api_dash, "/api/v1/circles")
    circle_reads = [call for call in api_dash if call["path"].startswith("/api/v1/circles/")]
    assert circle_reads
    assert circle_reads[0]["headers"]["Authorization"].startswith("Bearer ")
    assert "role" not in (circle_reads[0]["params"] or {})


def test_membertest_role_comes_from_the_server_and_blocks_payouts(api_dash):
    with app.server.test_request_context():
        identity = apply_signin("  membertest@example.test ", MEMBER_PW)
        assert identity is not None
        assert identity.username == "membertest"
        assert session["role"] == "member"
        text = str(render_shell("payouts", "admin"))
        assert session["role"] == "member"
        assert "Hold to release" not in text
        assert "Local Demo Circle · member" in text
        saved = {key: session[key] for key in session}
        sid = session["api_sid"]
    saved["role"] = "admin"
    saved["circles"] = [{"circle_id": 999, "name": "Fake Circle", "role": "admin"}]
    client = app.server.test_client()
    with client.session_transaction() as sess:
        sess.update(saved)
    response = client.get("/payouts?role=admin")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")
    assert "Hold to release" not in response.get_data(as_text=True)
    assert dash_api.VAULT.get(sid)["access_token"] not in response.get_data(as_text=True)


def test_personas_and_other_accounts_cannot_sign_in(api_dash):
    with app.server.test_request_context():
        assert apply_signin("kemi_a", ADMIN_PW) is None
        assert apply_signin("amina@example.test", ADMIN_PW) is None
        assert "role" not in session
    assert _paths(api_dash, "/api/v1/auth/login") == []


def test_wrong_password_does_not_open_a_session(api_dash):
    with app.server.test_request_context():
        page, _rev, error = next_state(
            {"type": "auth-btn", "action": "signin-submit"},
            "signin",
            0,
            "admintest",
            "not-the-password",
        )
        assert page == "signin"
        assert error == "Sign-in failed."
        assert "role" not in session
        assert dash_api.VAULT._rows == {}


def test_refresh_uses_the_test_clock_and_logout_drops_the_token(api_dash):
    with app.server.test_request_context():
        apply_signin("admintest", ADMIN_PW)
        sid = session["api_sid"]
        previous = dash_api.VAULT.get(sid)["access_token"]
        clock.advance(timedelta(minutes=16))
        status, me = dash_api.request("GET", "/api/v1/me", sid=sid)
        assert status == 200
        assert me["email"] == "admintest@example.test"
        refreshed = dash_api.VAULT.get(sid)["access_token"]
        assert refreshed != previous
        assert any(call["path"] == "/api/v1/auth/refresh" for call in api_dash)
        dash_api.logout(sid)
        assert dash_api.VAULT.get(sid) is None
        assert any(call["path"] == "/api/v1/auth/logout" for call in api_dash)
        replay = http.get("/api/v1/me", headers={"Authorization": f"Bearer {refreshed}"})
        assert replay.status_code == 401
        assert previous not in json.dumps({key: session.get(key) for key in ("username", "role", "api_sid")})


def test_admin_page_calls_audit_and_ledger_without_printing_tokens(api_dash):
    from backend.ledger import CREDIT, DEBIT, Posting, open_account, post_entry

    frozen = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
    clock.freeze(frozen)
    with database.SessionLocal() as db:
        open_account(
            db,
            code="asset:partner:circle-synth-dash",
            name="Partner clearing",
            kind="asset",
            circle_ref="circle-synth-dash",
        )
        open_account(
            db,
            code="liability:member-ada:circle-synth-dash",
            name="Member Ada contributions",
            kind="liability",
            circle_ref="circle-synth-dash",
            member_ref="member-ada",
        )
        post_entry(
            db,
            description="Contribution",
            reference="contrib-synth-dash",
            postings=[
                Posting("asset:partner:circle-synth-dash", DEBIT, 2575),
                Posting("liability:member-ada:circle-synth-dash", CREDIT, 2575),
            ],
        )
        admin = db.query(database.User).filter(database.User.email == "admintest@example.test").one()
        admin.platform_role = PLATFORM_ADMIN
        db.commit()
    with app.server.test_request_context():
        apply_signin("admintest", ADMIN_PW)
        token = dash_api.VAULT.get(session["api_sid"])["access_token"]
        text = str(render_shell("admin", "member"))
        assert "Checked 2026-04-01 12:00:00 UTC" in text
        assert "Audit log" in text
        assert "Ledger balances" in text
        assert "Not allowed." not in text
        assert "The ledger view is not available from this API." not in text
        assert "£25.75" in text
        assert "2575" in text
        assert token not in text
        assert "admintest@example.test" not in text
        assert ADMIN_PW not in text
    assert _paths(api_dash, "/api/v1/admin/audit")
    assert _paths(api_dash, "/api/v1/admin/ledger")
    audit_call = _paths(api_dash, "/api/v1/admin/audit")[-1]
    assert audit_call["headers"]["Authorization"].startswith("Bearer ")
    assert "role" not in (audit_call["params"] or {})


def test_circle_member_is_refused_the_audit_log(api_dash):
    with app.server.test_request_context():
        apply_signin("membertest", MEMBER_PW)
        text = str(render_shell("admin", "admin"))
        assert "Not allowed." in text
        assert "The ledger view is not available from this API." not in text
        assert "£25.75" not in text
        token = dash_api.VAULT.get(session["api_sid"])["access_token"]
        assert token not in text


def test_create_and_join_use_the_api(api_dash):
    with app.server.test_request_context():
        apply_signin("admintest", ADMIN_PW)
        admin_sid = session["api_sid"]
        status, created = dash_api.request(
            "POST",
            "/api/v1/circles",
            json_body={"name": "Synth Circle"},
            sid=admin_sid,
        )
        assert status == 201, created
        circle_id = created["circle_id"]
        dash_api.sync_session_force()
        assert any(circle["name"] == "Synth Circle" and circle["role"] == "admin" for circle in session["circles"])
    with app.server.test_request_context():
        apply_signin("membertest", MEMBER_PW)
        status, joined = dash_api.request("POST", f"/api/v1/circles/{circle_id}/join", sid=session["api_sid"])
        assert status == 200, joined
        dash_api.sync_session_force()
        match = [circle for circle in session["circles"] if circle["name"] == "Synth Circle"]
        assert match and match[0]["role"] == "member"
        payouts = dash_api.request("GET", f"/api/v1/circles/{circle_id}/payouts", sid=session["api_sid"])
        assert payouts[0] == 403


def test_signup_accepts_only_example_test_addresses(api_dash):
    signup = {
        "first": "Ada",
        "last": "Example",
        "email": "ada.screen@example.test",
        "phone": "07000000000",
        "password": "correct-horse",
        "confirm": "correct-horse",
    }
    with app.server.test_request_context():
        page, _rev, error = next_state(
            {"type": "auth-btn", "action": "signup-submit"},
            "getstarted-1",
            0,
            "",
            "",
            signup,
        )
        assert page == "signin"
        assert error == ""
        refused = dict(signup)
        refused["email"] = "ada.screen@example.com"
        page, _rev, error = next_state(
            {"type": "auth-btn", "action": "signup-submit"},
            "getstarted-1",
            0,
            "",
            "",
            refused,
        )
        assert page == "getstarted-1"
        assert error == "Use an @example.test address."
        assert apply_signin("ada.screen@example.test", "correct-horse") is None
    posted = _paths(api_dash, "/api/v1/auth/signup")
    assert len(posted) == 1
    assert posted[0]["body"]["email"] == "ada.screen@example.test"
    assert "role" not in posted[0]["body"]


def test_demo_sign_in_is_refused_outside_local_and_dev(api_dash, monkeypatch):
    monkeypatch.setenv("AJO_ENV", "production")
    with app.server.test_request_context():
        assert apply_signin("admintest", ADMIN_PW) is None
    assert _paths(api_dash, "/api/v1/auth/login") == []


ADMIN_ENDPOINTS = {"/api/v1/admin/audit", "/api/v1/admin/ledger"}
OTHER_PATHS = (
    "/",
    "/signin",
    "/dashboard",
    "/members",
    "/circle",
    "/wallet",
    "/settings",
    "/join",
    "/support",
    "/credit",
    "/autoloan",
    "/payouts",
)
RENDER_OUTPUT = "..app-shell.children...signin-dock.style.."


def _audit_count() -> int:
    with database.SessionLocal() as db:
        return db.query(database.AuditLog).count()


def _audit_actions() -> list[str]:
    with database.SessionLocal() as db:
        return [row.action for row in db.query(database.AuditLog).order_by(database.AuditLog.id).all()]


def _render(client, pathname: str) -> str:
    response = client.post(
        "/_dash-update-component",
        json={
            "output": RENDER_OUTPUT,
            "outputs": [
                {"id": "app-shell", "property": "children"},
                {"id": "signin-dock", "property": "style"},
            ],
            "inputs": [
                {"id": "url", "property": "pathname", "value": pathname},
                {"id": "store-auth-rev", "property": "data", "value": 1},
            ],
            "changedPropIds": ["url.pathname"],
            "state": [],
        },
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_data(as_text=True)


def _client_with_session(saved: dict):
    client = app.server.test_client()
    with client.session_transaction() as sess:
        sess.update(saved)
    return client


def test_other_pages_do_not_call_admin_audit_or_ledger(api_dash):
    """A page that is not the admin screen never touches the audit or ledger APIs."""
    with database.SessionLocal() as db:
        admin = db.query(database.User).filter(database.User.email == "admintest@example.test").one()
        admin.platform_role = PLATFORM_ADMIN
        db.commit()
    for username, password, opened in (
        ("admintest", ADMIN_PW, {"audit_log_read", "financial_data_viewed"}),
        ("membertest", MEMBER_PW, {"audit_log_denied"}),
    ):
        with app.server.test_request_context():
            assert apply_signin(username, password) is not None
            before = _audit_count()
            saved = dict(session)
        start = len(api_dash)
        client = _client_with_session(saved)
        for path in OTHER_PATHS:
            _render(client, path)
        assert [call["path"] for call in api_dash[start:] if call["path"] in ADMIN_ENDPOINTS] == []
        assert _audit_count() == before
        _render(client, "/admin")
        hit = {call["path"] for call in api_dash[start:] if call["path"] in ADMIN_ENDPOINTS}
        assert hit == ADMIN_ENDPOINTS
        assert _audit_count() > before
        assert opened <= set(_audit_actions())
    with app.server.test_request_context():
        dash_api.logout(session.get("api_sid"))
    start = len(api_dash)
    before = _audit_count()
    guest = app.server.test_client()
    _render(guest, "/signin")
    _render(guest, "/dashboard")
    assert [call["path"] for call in api_dash[start:] if call["path"] in ADMIN_ENDPOINTS] == []
    assert _audit_count() == before


def test_unreachable_api_is_distinct_from_a_rejected_sign_in(api_dash, monkeypatch):
    from backend.stub_auth import SIGNIN_FAILED

    real = dash_api._transport_send

    def unavailable(status):
        def send(method, path, body, headers, params):
            return status, None

        dash_api.install_transport_for_tests(send)
        with app.server.test_request_context():
            page, _rev, error = next_state(
                {"type": "auth-btn", "action": "signin-submit"},
                "signin",
                0,
                "admintest",
                ADMIN_PW,
            )
            assert page == "signin"
            assert error == dash_api.SERVICE_UNAVAILABLE
            assert error != SIGNIN_FAILED
            assert dash_api.VAULT._rows == {}

    unavailable(0)
    unavailable(503)
    unavailable(408)

    def time_out(method, path, body, headers, params):
        raise TimeoutError("timed out")

    dash_api.install_transport_for_tests(time_out)
    with app.server.test_request_context():
        page, _rev, error = next_state(
            {"type": "auth-btn", "action": "signin-submit"},
            "signin",
            0,
            "admintest",
            ADMIN_PW,
        )
        assert page == "signin"
        assert error == dash_api.SERVICE_UNAVAILABLE
        assert dash_api.VAULT._rows == {}

    dash_api.install_transport_for_tests(None)
    monkeypatch.setenv("AJO_API_BASE", "http://127.0.0.1:9")

    def boom(*_args, **kwargs):
        assert kwargs.get("timeout") == dash_api.API_TIMEOUT_SECONDS
        raise TimeoutError("timed out")

    monkeypatch.setattr(dash_api.urllib.request, "urlopen", boom)
    assert 3 <= dash_api.API_TIMEOUT_SECONDS <= 5
    status, payload = dash_api._urllib_send("POST", "/api/v1/auth/login", {}, {}, None)
    assert (status, payload) == (0, None)

    def refused(*_args, **_kwargs):
        import urllib.error

        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(dash_api.urllib.request, "urlopen", refused)
    status, payload = dash_api._urllib_send("POST", "/api/v1/auth/login", {}, {}, None)
    assert (status, payload) == (0, None)

    dash_api.install_transport_for_tests(real)
    with app.server.test_request_context():
        page, _rev, error = next_state(
            {"type": "auth-btn", "action": "signin-submit"},
            "signin",
            0,
            "admintest",
            "wrong-password",
        )
        assert page == "signin"
        assert error == SIGNIN_FAILED

    def me_down(method, path, body, headers, params):
        if path.split("?", 1)[0] == "/api/v1/me":
            return 503, {"detail": "unavailable"}
        return real(method, path, body, headers, params)

    dash_api.install_transport_for_tests(me_down)
    with app.server.test_request_context():
        page, _rev, error = next_state(
            {"type": "auth-btn", "action": "signin-submit"},
            "signin",
            0,
            "membertest",
            MEMBER_PW,
        )
        assert page == "signin"
        assert error == dash_api.SERVICE_UNAVAILABLE
        assert dash_api.VAULT._rows == {}


def test_signed_in_session_survives_an_unreachable_api(api_dash):
    real = dash_api._transport_send
    with app.server.test_request_context():
        assert apply_signin("admintest", ADMIN_PW) is not None
        sid = session["api_sid"]
        saved = dict(session)

    def outage(status):
        def send(method, path, body, headers, params):
            pure = path.split("?", 1)[0]
            if pure == "/api/v1/me" or pure.startswith("/api/v1/circles"):
                return status, None
            return real(method, path, body, headers, params)

        dash_api.install_transport_for_tests(send)
        client = _client_with_session(saved)
        body = _render(client, "/dashboard")
        assert '"display":"none"' in body
        assert dash_api.SERVICE_UNAVAILABLE in body
        with client.session_transaction() as sess:
            assert sess.get("role") == "admin"
            assert sess.get("api_sid") == sid
            assert sess.get("circles")
        assert dash_api.VAULT.get(sid) is not None

    outage(0)
    outage(503)

    def refresh_down(method, path, body, headers, params):
        pure = path.split("?", 1)[0]
        if pure == "/api/v1/auth/refresh":
            return 503, None
        if pure == "/api/v1/me":
            return 401, {"detail": "expired"}
        return real(method, path, body, headers, params)

    dash_api.install_transport_for_tests(refresh_down)
    client = _client_with_session(saved)
    body = _render(client, "/members")
    assert dash_api.SERVICE_UNAVAILABLE in body
    with client.session_transaction() as sess:
        assert sess.get("role") == "admin"
        assert sess.get("api_sid") == sid
    assert dash_api.VAULT.get(sid) is not None

    def rejected(method, path, body, headers, params):
        pure = path.split("?", 1)[0]
        if pure in {"/api/v1/me", "/api/v1/auth/refresh"}:
            return 401, {"detail": "rejected"}
        return real(method, path, body, headers, params)

    dash_api.install_transport_for_tests(rejected)
    client = _client_with_session(saved)
    body = _render(client, "/dashboard")
    with client.session_transaction() as sess:
        assert sess.get("role") is None
        assert "api_sid" not in sess
    assert '"display":"none"' not in body
    assert dash_api.SERVICE_UNAVAILABLE not in body


def _signed_in_client(username, password):
    with app.server.test_request_context():
        assert apply_signin(username, password) is not None
        sid = session["api_sid"]
        saved = dict(session)
    return sid, saved, _client_with_session(saved)


@pytest.mark.parametrize("path", ["/dashboard", "/members", "/support", "/payouts"])
@pytest.mark.parametrize("failure", ["connection", "timeout"])
def test_signed_in_pages_show_unavailable_when_refresh_fails(api_dash, path, failure):
    real = dash_api._transport_send
    sid, saved, client = _signed_in_client("admintest", ADMIN_PW)

    def send(method, call_path, body, headers, params):
        pure = call_path.split("?", 1)[0]
        if pure == "/api/v1/me" or pure.startswith("/api/v1/circles"):
            if failure == "timeout":
                raise TimeoutError("timed out")
            return 0, None
        return real(method, call_path, body, headers, params)

    dash_api.install_transport_for_tests(send)
    rendered = _render(client, path)
    assert dash_api.SERVICE_UNAVAILABLE in rendered
    assert "payouts-tracker" not in rendered
    assert "Hold to release" not in rendered
    assert "· admin" not in rendered
    assert '"href":"/admin"' not in rendered
    assert '"href":"/payouts"' not in rendered
    with client.session_transaction() as sess:
        assert sess.get("role") == "admin"
        assert sess.get("api_sid") == sid
        assert sess.get("circles") == saved["circles"]
    assert dash_api.VAULT.get(sid) is not None
    assert '"display":"none"' in rendered


def test_timeout_on_the_first_circle_skips_the_rest(api_dash):
    with app.server.test_request_context():
        assert apply_signin("admintest", ADMIN_PW) is not None
        sid = session["api_sid"]
        for name in ("Synth North", "Synth South"):
            status, created = dash_api.request(
                "POST",
                "/api/v1/circles",
                json_body={"name": name},
                sid=sid,
            )
            assert status == 201, created
        dash_api.sync_session_force()
        circle_ids = [circle["circle_id"] for circle in session["circles"]]
        assert len(circle_ids) >= 3
        saved = dict(session)
    real = dash_api._transport_send
    detail_calls: list[str] = []
    delay = 0.75

    def send(method, path, body, headers, params):
        pure = path.split("?", 1)[0]
        parts = pure.strip("/").split("/")
        if len(parts) == 4 and parts[:3] == ["api", "v1", "circles"] and parts[3].isdigit():
            detail_calls.append(pure)
            time.sleep(delay)
            raise TimeoutError("timed out")
        return real(method, path, body, headers, params)

    dash_api.install_transport_for_tests(send)
    client = _client_with_session(saved)
    started = time.monotonic()
    rendered = _render(client, "/members")
    elapsed = time.monotonic() - started
    assert len(detail_calls) == 1
    assert elapsed < delay * 2
    assert elapsed < dash_api.API_TIMEOUT_SECONDS * len(circle_ids)
    assert dash_api.SERVICE_UNAVAILABLE in rendered
    assert "· admin" not in rendered
    with client.session_transaction() as sess:
        assert sess.get("role") == "admin"
        assert sess.get("api_sid") == sid


def test_stub_sign_in_remains_when_the_api_base_is_unset(tmp_path, monkeypatch):
    path = tmp_path / "stub-users.json"
    path.write_text(json.dumps({"admintest": ADMIN_PW, "membertest": MEMBER_PW}), encoding="utf-8")
    monkeypatch.setenv("STUB_USERS_FILE", str(path))
    monkeypatch.setenv("ALLOW_LOCAL_STUB_LOGIN", "true")
    monkeypatch.setenv("DASH_HOST", "127.0.0.1")
    monkeypatch.setenv("AJO_ENV", "local")
    monkeypatch.delenv("AJO_API_BASE", raising=False)
    dash_api.install_transport_for_tests(None)
    with app.server.test_request_context():
        page, _rev, error = next_state(
            {"type": "auth-btn", "action": "signin-submit"},
            "signin",
            0,
            "admintest",
            ADMIN_PW,
        )
        assert page == "home"
        assert error == ""
        assert session["role"] == "admin"
        assert "api_sid" not in session
