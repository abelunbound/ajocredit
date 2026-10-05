"""Local-only admintest / membertest sign-in.

Covers successful local login for both roles, refusal when the stub flag is
off or the process is not local, startup failure when the flag is enabled
outside localhost, and the member being unable to open admin-only pages.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from flask import session

from app_dash_web import app, next_state, render_page, render_shell
from pages.signin import layout as signin_layout
from stub_auth import (
    SIGNIN_FAILED,
    authenticate,
    enforce_local_stub_policy,
    gate_page,
    nav_entries,
)
from pages.data import NAV

ADMIN_PW = "pw-admin"
MEMBER_PW = "pw-member"


def _write_credentials(path: Path, admin_pw=ADMIN_PW, member_pw=MEMBER_PW):
    path.write_text(
        json.dumps({"admintest": admin_pw, "membertest": member_pw}),
        encoding="utf-8",
    )


def _local_source(path: Path, **overrides):
    source = {
        "ALLOW_LOCAL_STUB_LOGIN": "true",
        "DASH_HOST": "127.0.0.1",
        "AJO_ENV": "local",
        "STUB_USERS_FILE": str(path),
    }
    source.update(overrides)
    return source


@pytest.fixture
def creds(tmp_path):
    path = tmp_path / "stub-users.json"
    _write_credentials(path)
    return path


@pytest.fixture
def local_env(creds, monkeypatch):
    monkeypatch.setenv("ALLOW_LOCAL_STUB_LOGIN", "true")
    monkeypatch.setenv("DASH_HOST", "127.0.0.1")
    monkeypatch.setenv("AJO_ENV", "local")
    monkeypatch.setenv("STUB_USERS_FILE", str(creds))
    return creds


def _run_import(module, env):
    child_env = os.environ.copy()
    for name in (
        "ALLOW_LOCAL_STUB_LOGIN",
        "DASH_HOST",
        "AJO_ENV",
        "STUB_USERS_FILE",
    ):
        child_env.pop(name, None)
    child_env.update(env)
    return subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        env=child_env,
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.abspath(__file__)),
    )


def _shell_text(page, client_value="admin"):
    return str(render_shell(page, client_value))


def _signin(username, password):
    return next_state(
        {"type": "auth-btn", "action": "signin-submit"},
        "signin",
        0,
        username,
        password,
    )


class TestLocalLogin:
    def test_admintest_signs_in_locally(self, local_env):
        identity = authenticate("admintest", ADMIN_PW)
        assert identity is not None
        assert identity.username == "admintest"
        assert identity.role == "admin"

        with app.server.test_request_context():
            page, _rev, error = _signin("admintest", ADMIN_PW)
            assert page == "home"
            assert error == ""
            assert session["role"] == "admin"
            assert session["username"] == "admintest"
            text = _shell_text("home", "member")
            assert "PayoutsTracker" in text
            assert "Admin" in text
            assert "role-btn" not in text
            assert "@admintest" in text

    def test_membertest_signs_in_locally(self, local_env):
        identity = authenticate("membertest", MEMBER_PW)
        assert identity is not None
        assert identity.username == "membertest"
        assert identity.role == "member"

        with app.server.test_request_context():
            page, _rev, error = _signin("membertest", MEMBER_PW)
            assert page == "home"
            assert error == ""
            assert session["role"] == "member"
            text = _shell_text("home", "admin")
            assert "PayoutsTracker" not in text
            assert "Member" in text
            assert "role-btn" not in text
            assert "@membertest" in text

    @pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
    def test_loopback_hosts_are_local(self, creds, host):
        source = _local_source(creds, DASH_HOST=host)
        assert authenticate("admintest", ADMIN_PW, source) is not None
        enforce_local_stub_policy(source)


class TestStubRefused:
    def test_stub_refused_when_flag_off(self, creds, monkeypatch):
        monkeypatch.setenv("ALLOW_LOCAL_STUB_LOGIN", "false")
        monkeypatch.setenv("DASH_HOST", "127.0.0.1")
        monkeypatch.setenv("AJO_ENV", "local")
        monkeypatch.setenv("STUB_USERS_FILE", str(creds))

        assert authenticate("admintest", ADMIN_PW) is None
        assert authenticate("membertest", MEMBER_PW) is None
        enforce_local_stub_policy()

        with app.server.test_request_context():
            page, _rev, error = _signin("admintest", ADMIN_PW)
            assert page == "signin"
            assert error == SIGNIN_FAILED
            assert "role" not in session

    def test_stub_refused_when_host_is_not_local(self, creds):
        source = _local_source(creds, DASH_HOST="0.0.0.0")
        assert authenticate("admintest", ADMIN_PW, source) is None
        with pytest.raises(SystemExit) as exc:
            enforce_local_stub_policy(source)
        assert exc.value.code == 1

    def test_stub_refused_when_env_is_not_local(self, creds):
        source = _local_source(creds, AJO_ENV="production")
        assert authenticate("membertest", MEMBER_PW, source) is None
        with pytest.raises(SystemExit) as exc:
            enforce_local_stub_policy(source)
        assert exc.value.code == 1

    def test_unset_host_is_not_treated_as_localhost(self, creds):
        source = _local_source(creds, DASH_HOST="")
        assert authenticate("admintest", ADMIN_PW, source) is None
        with pytest.raises(SystemExit):
            enforce_local_stub_policy(source)

    def test_wrong_password_and_unknown_user_are_refused(self, local_env):
        assert authenticate("admintest", "nope") is None
        assert authenticate("someoneelse", ADMIN_PW) is None

    def test_placeholder_passwords_do_not_sign_in(self, tmp_path):
        path = tmp_path / "stub-users.json"
        _write_credentials(path, "replace-me", "replace-me")
        source = _local_source(path)
        assert authenticate("admintest", "replace-me", source) is None
        with pytest.raises(SystemExit):
            enforce_local_stub_policy(source)

    def test_example_file_cannot_be_the_credentials_file(self):
        source = _local_source(Path("local/stub-users.example.json"))
        assert authenticate("admintest", "replace-me", source) is None
        with pytest.raises(SystemExit):
            enforce_local_stub_policy(source)

    def test_file_cannot_grant_admin_to_membertest(self, tmp_path):
        path = tmp_path / "stub-users.json"
        path.write_text(
            json.dumps(
                {
                    "admintest": ADMIN_PW,
                    "membertest": {"password": MEMBER_PW, "role": "admin"},
                }
            ),
            encoding="utf-8",
        )
        source = _local_source(path)
        with pytest.raises(SystemExit):
            enforce_local_stub_policy(source)


class TestStartupFailsLoudly:
    def test_import_fails_when_flag_on_and_host_is_public(self):
        result = _run_import(
            "app_dash_web",
            {
                "ALLOW_LOCAL_STUB_LOGIN": "true",
                "DASH_HOST": "0.0.0.0",
                "AJO_ENV": "local",
            },
        )
        assert result.returncode == 1
        assert "ALLOW_LOCAL_STUB_LOGIN" in result.stderr
        assert "Refusing to start" in result.stderr
        assert ADMIN_PW not in result.stderr

    def test_import_fails_when_flag_on_in_production_env(self, creds):
        result = _run_import(
            "app_dash_web",
            {
                "ALLOW_LOCAL_STUB_LOGIN": "true",
                "DASH_HOST": "127.0.0.1",
                "AJO_ENV": "production",
                "STUB_USERS_FILE": str(creds),
            },
        )
        assert result.returncode == 1
        assert "not a local-only environment" in result.stderr
        assert "AJO_ENV" in result.stderr

    def test_api_import_fails_when_stub_flag_is_not_local(self):
        result = _run_import(
            "api",
            {
                "ALLOW_LOCAL_STUB_LOGIN": "true",
                "DASH_HOST": "0.0.0.0",
                "AJO_ENV": "staging",
                "JWT_SECRET_KEY": "a" * 32,
                "DATABASE_URL": "postgresql://test:test@localhost/test",
            },
        )
        assert result.returncode == 1
        assert "ALLOW_LOCAL_STUB_LOGIN" in result.stderr
        assert "Refusing to start" in result.stderr

    def test_import_succeeds_for_explicit_local_flag(self, creds):
        result = _run_import(
            "app_dash_web",
            {
                "ALLOW_LOCAL_STUB_LOGIN": "true",
                "DASH_HOST": "localhost",
                "AJO_ENV": "local",
                "STUB_USERS_FILE": str(creds),
            },
        )
        assert result.returncode == 0, result.stderr

    def test_flag_off_does_not_block_a_public_bind(self):
        result = _run_import(
            "app_dash_web",
            {
                "ALLOW_LOCAL_STUB_LOGIN": "false",
                "DASH_HOST": "0.0.0.0",
                "AJO_ENV": "production",
            },
        )
        assert result.returncode == 0, result.stderr


class TestMemberCannotReachAdminPages:
    def test_member_cannot_open_payouts(self, local_env):
        with app.server.test_request_context():
            _signin("membertest", MEMBER_PW)
            assert gate_page("payouts", session.get("role")) == "home"
            text = _shell_text("payouts", "admin")
            assert "PayoutsTracker" not in text
            assert "Hold to release" not in text
            assert "Release payout" not in text
            page, _rev, _error = next_state(
                {"type": "nav-btn", "page": "payouts"},
                "home",
                1,
                "",
                "",
            )
            assert page == "home"
            assert session["role"] == "member"

    def test_admin_can_open_payouts(self, local_env):
        with app.server.test_request_context():
            _signin("admintest", ADMIN_PW)
            text = _shell_text("payouts", "member")
            assert "PayoutsTracker" in text
            assert "Hold to release" in text

    def test_render_callback_ignores_client_role(self, local_env):
        client = app.server.test_client()
        with client.session_transaction() as sess:
            sess["username"] = "membertest"
            sess["role"] = "member"
        response = client.post(
            "/_dash-update-component",
            json={
                "output": "..app-shell.children...signin-dock.style..",
                "outputs": [
                    {"id": "app-shell", "property": "children"},
                    {"id": "signin-dock", "property": "style"},
                ],
                "inputs": [
                    {"id": "store-page", "property": "data", "value": "payouts"},
                    {"id": "store-auth-rev", "property": "data", "value": "admin"},
                ],
                "changedPropIds": ["store-page.data"],
                "state": [],
            },
        )
        body = response.get_data(as_text=True)
        assert response.status_code == 200
        assert "PayoutsTracker" not in body
        assert "Hold to release" not in body
        assert "Member" in body

    def test_forged_session_cookie_does_not_grant_admin(self):
        client = app.server.test_client()
        client.set_cookie("session", "admintest-admin")
        response = client.post(
            "/_dash-update-component",
            json={
                "output": "..app-shell.children...signin-dock.style..",
                "outputs": [
                    {"id": "app-shell", "property": "children"},
                    {"id": "signin-dock", "property": "style"},
                ],
                "inputs": [
                    {"id": "store-page", "property": "data", "value": "payouts"},
                    {"id": "store-auth-rev", "property": "data", "value": 1},
                ],
                "changedPropIds": ["store-page.data"],
                "state": [],
            },
        )
        body = response.get_data(as_text=True)
        assert "PayoutsTracker" not in body
        assert "Hold to release" not in body

    def test_member_render_page_hides_admin_payout_actions(self):
        text = str(render_page("payouts", "member"))
        assert "Hold to release" not in text
        assert "switch role" not in text

    def test_nav_hides_payouts_tracker_for_member(self):
        member_labels = [label for _key, label, _icon in nav_entries(NAV, "member")]
        admin_labels = [label for _key, label, _icon in nav_entries(NAV, "admin")]
        assert "PayoutsTracker" not in member_labels
        assert "PayoutsTracker" in admin_labels


class TestRoleToggleRemoved:
    def test_no_role_control_in_layout_or_signin_defaults(self):
        layout = str(app.layout)
        assert "role-btn" not in layout
        assert "store-role" not in layout
        form = str(signin_layout())
        assert "kemi@example.com" not in form
        assert 'value="password"' not in form

    def test_credentials_template_is_ignored_real_file(self):
        example = json.loads(Path("local/stub-users.example.json").read_text(encoding="utf-8"))
        assert example == {"admintest": "replace-me", "membertest": "replace-me"}
        env_example = Path(".env.example").read_text(encoding="utf-8")
        assert "ALLOW_LOCAL_STUB_LOGIN=false" in env_example
        assert "ALLOW_LOCAL_STUB_LOGIN=true" not in env_example
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", "local/stub-users.json"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        assert ignored.returncode == 0
