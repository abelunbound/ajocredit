"""Dash forgot-password and reset-password pages.

The token stays in the fragment until the page strips it, then moves only in
the reset POST body. Forgot-password shows one message for every address.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess

import pytest
from dash import no_update
from flask import session

import dash_api
from app_dash_web import (
    app,
    open_forgot_password,
    page_from_pathname,
    render_shell,
    send_forgot_password,
    submit_new_password,
)
from pages.password_flow import (
    CAPTURE_RESET_TOKEN_JS,
    NEUTRAL_FORGOT,
    forgot_message,
    reset_submission,
)
from pages.signin import layout as signin_layout

TOKEN = "reset-token-example"
NEW_PASSWORD = "new-password-1"
EXPIRED = "This reset link is invalid or has expired."
LIMITED = "Too many attempts. Try again later."


@pytest.fixture
def transport(monkeypatch):
    calls = []

    def install(handler):
        def send(method, path, body, headers, params):
            calls.append(
                {
                    "method": method,
                    "path": path,
                    "body": body,
                    "headers": dict(headers),
                    "params": params,
                }
            )
            return handler(body)

        monkeypatch.setenv("AJO_API_BASE", "http://127.0.0.1:8000")
        dash_api.install_transport_for_tests(send)
        return calls

    yield install
    dash_api.install_transport_for_tests(None)
    dash_api.VAULT._rows.clear()


def test_signin_forgot_button_opens_an_email_form():
    text = str(signin_layout())
    assert "Forgot password?" in text
    assert "forgot-email" in text
    assert "forgot-submit" in text
    assert open_forgot_password(1) == {"display": "block"}
    assert open_forgot_password(0) is no_update


def test_forgot_message_is_neutral_for_known_and_unknown_emails(transport):
    details = {
        "membertest@example.test": "This address is registered.",
        "missing@example.test": "No account for that email.",
    }

    def handler(body):
        return 200, {"detail": details[body["email"]]}

    calls = transport(handler)
    known = forgot_message("membertest@example.test")
    unknown = forgot_message("missing@example.test")
    assert known == unknown == NEUTRAL_FORGOT
    assert [call["body"]["email"] for call in calls] == [
        "membertest@example.test",
        "missing@example.test",
    ]
    assert all(call["path"] == "/api/v1/auth/password/forgot" for call in calls)
    assert send_forgot_password(1, "membertest@example.test") == NEUTRAL_FORGOT
    assert send_forgot_password(1, "missing@example.test") == NEUTRAL_FORGOT


def test_forgot_form_shows_the_api_429_and_the_outage_message(transport, monkeypatch):
    def limited(_body):
        return 429, {"detail": LIMITED}

    transport(limited)
    assert forgot_message("membertest@example.test") == LIMITED
    assert forgot_message("missing@example.test") == LIMITED

    def down(_body):
        return 503, {"detail": "Email cannot be sent until a mail provider is configured."}

    dash_api.install_transport_for_tests(
        lambda method, path, body, headers, params: down(body)
    )
    assert forgot_message("membertest@example.test") == dash_api.SERVICE_UNAVAILABLE
    monkeypatch.delenv("AJO_API_BASE", raising=False)
    dash_api.install_transport_for_tests(None)
    assert forgot_message("ada@example.test") == dash_api.SERVICE_UNAVAILABLE


def test_reset_page_is_public_and_posts_the_token_only_in_the_body(transport):
    assert page_from_pathname("/reset-password") == "reset-password"
    assert page_from_pathname("/reset-password/") == "reset-password"
    client = app.server.test_client()
    response = client.get("/reset-password")
    assert response.status_code == 200
    assert response.request.path == "/reset-password"
    with app.server.test_request_context():
        body = str(render_shell("reset-password"))
    assert "Choose a new password" in body
    assert TOKEN not in body

    seen = {}

    def handler(body):
        seen["body"] = body
        return 400, {"detail": EXPIRED}

    calls = transport(handler)
    outcome, message = reset_submission(TOKEN, NEW_PASSWORD, NEW_PASSWORD)
    assert outcome == "stay"
    assert message == EXPIRED
    assert calls[0]["method"] == "POST"
    assert calls[0]["path"] == "/api/v1/auth/password/reset"
    assert calls[0]["params"] is None
    assert TOKEN not in calls[0]["path"]
    assert calls[0]["body"] == {"token": TOKEN, "password": NEW_PASSWORD}
    assert "authorization" not in {key.lower() for key in calls[0]["headers"]}

    def used(body):
        return 400, {"detail": "This reset link was already used."}

    dash_api.install_transport_for_tests(
        lambda method, path, body, headers, params: used(body)
    )
    assert reset_submission(TOKEN, NEW_PASSWORD, NEW_PASSWORD)[1] == "This reset link was already used."

    def limited(body):
        return 429, {"detail": LIMITED}

    dash_api.install_transport_for_tests(
        lambda method, path, body, headers, params: limited(body)
    )
    assert reset_submission(TOKEN, NEW_PASSWORD, NEW_PASSWORD) == ("stay", LIMITED)
    assert reset_submission("", NEW_PASSWORD, NEW_PASSWORD)[0] == "stay"
    mismatch = reset_submission(TOKEN, NEW_PASSWORD, "other-password-1")
    assert mismatch == ("stay", "Passwords do not match.")


def test_successful_reset_clears_the_session_and_does_not_log_the_token(transport, caplog):
    def handler(_body):
        return 200, {"detail": "Your password has been reset. Sign in again."}

    transport(handler)
    caplog.set_level(logging.DEBUG)
    with app.server.test_request_context():
        session["role"] = "member"
        session["username"] = "membertest"
        session["email"] = "membertest@example.test"
        session["api_sid"] = "opaque-sid"
        dash_api.VAULT._rows["opaque-sid"] = {
            "access_token": "access-example",
            "refresh_token": "refresh-example",
        }
        path, notice, error = submit_new_password(1, TOKEN, NEW_PASSWORD, NEW_PASSWORD)
        assert path == "/signin"
        assert notice == "Your password has been reset. Sign in again."
        assert error == ""
        assert "role" not in session
        assert "api_sid" not in session
        assert dash_api.VAULT.get("opaque-sid") is None
    assert TOKEN not in caplog.text
    assert NEW_PASSWORD not in caplog.text
    assert "access-example" not in caplog.text


def _settings_reset(client):
    response = client.post(
        "/_dash-update-component",
        json={
            "output": "settings-feedback.children",
            "outputs": {"id": "settings-feedback", "property": "children"},
            "inputs": [
                {
                    "id": {"type": "settings-action", "action": "reset-password"},
                    "property": "n_clicks",
                    "value": 1,
                }
            ],
            "changedPropIds": ['{"action":"reset-password","type":"settings-action"}.n_clicks'],
            "state": [
                {"id": "settings-address-line", "property": "value", "value": ""},
                {"id": "settings-city", "property": "value", "value": ""},
                {"id": "settings-postcode", "property": "value", "value": ""},
                {"id": "settings-phone", "property": "value", "value": ""},
            ],
        },
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()


def test_settings_reset_uses_the_signed_in_email(transport):
    def handler(_body):
        return 200, {"detail": "registered"}

    calls = transport(handler)
    client = app.server.test_client()
    with client.session_transaction() as sess:
        sess["role"] = "member"
        sess["username"] = "membertest"
        sess["email"] = "membertest@example.test"
    payload = _settings_reset(client)
    assert payload["response"]["settings-feedback"]["children"] == NEUTRAL_FORGOT
    assert calls[-1]["body"] == {"email": "membertest@example.test"}

    with client.session_transaction() as sess:
        sess["role"] = "admin"
        sess["username"] = "admintest"
        sess.pop("email", None)
    payload = _settings_reset(client)
    assert payload["response"]["settings-feedback"]["children"] == NEUTRAL_FORGOT
    assert calls[-1]["body"] == {"email": "admintest@example.test"}


def test_reset_callback_shows_api_errors_through_the_dash_endpoint(transport):
    def handler(_body):
        return 429, {"detail": LIMITED}

    calls = transport(handler)
    with app.server.test_request_context():
        path, notice, error = submit_new_password(1, TOKEN, NEW_PASSWORD, NEW_PASSWORD)
    assert path is no_update
    assert notice is no_update
    assert error == LIMITED
    assert calls[0]["body"]["token"] == TOKEN
    assert TOKEN not in calls[0]["path"]
    assert notice is no_update or notice == no_update


def test_page_boot_script_strips_the_fragment_and_does_not_log():
    page = app.server.test_client().get("/reset-password").get_data(as_text=True)
    script = page.split("<script>", 1)[1].split("</script>", 1)[0]
    assert "ajoCaptureResetToken" in script
    assert "replaceState" in script
    assert "console.log" not in script
    assert "console.debug" not in script
    assert "console.info" not in script
    assert page.count("replaceState") >= 2
    assert "__ajoResetToken" in page
    assert TOKEN not in page
    assert "console.log" not in CAPTURE_RESET_TOKEN_JS

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    program = (
        CAPTURE_RESET_TOKEN_JS
        + """
const loc = {pathname: "/reset-password", search: "?from=email", hash: "#token="""
        + TOKEN
        + """&extra=1", state: null};
const hist = {state: null, url: "", replaceState(state, title, url) { this.url = url; loc.hash = ""; }};
const token = ajoCaptureResetToken(loc, hist);
if (token !== """
        + json.dumps(TOKEN)
        + """) throw new Error("token");
if (hist.url !== "/reset-password?from=email") throw new Error("url " + hist.url);
if (hist.url.indexOf("token") !== -1) throw new Error("token left in url");
const other = ajoCaptureResetToken({pathname: "/signin", search: "", hash: "#token=nope"}, {replaceState() { throw new Error("stripped other page"); }});
if (other !== "") throw new Error("other page");
"""
    )
    ran = subprocess.run([node, "-e", program], capture_output=True, text=True, check=False)
    assert ran.returncode == 0, ran.stderr
