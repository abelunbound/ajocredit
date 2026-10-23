"""Dash /verify-email page for the link in the verification email."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess

import pytest

import frontend.dash_api as dash_api
from frontend.app_dash_web import app, confirm_email_link, page_from_pathname, render_shell
from frontend.pages.verify_email import CAPTURE_VERIFY_TOKEN_JS

TOKEN = "verify-token-example"
VERIFIED = "Your email is verified."
EXPIRED = "This verification link is invalid or has expired."
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


def test_verify_page_is_public_and_links_to_sign_in():
    assert page_from_pathname("/verify-email") == "verify-email"
    client = app.server.test_client()
    response = client.get("/verify-email")
    assert response.status_code == 200
    assert response.request.path == "/verify-email"
    with app.server.test_request_context():
        assert str(render_shell("verify-email")) == "Div()" or "Hold to release" not in str(render_shell("verify-email"))
    page = client.get("/_dash-layout").get_data(as_text=True)
    assert "Confirm your email" in page
    assert '"children":"Sign in"' in page
    assert "verify-message" in page
    assert TOKEN not in page


def test_confirm_callback_shows_the_api_success_message(transport, caplog):
    def handler(_body):
        return 200, {"detail": VERIFIED}

    calls = transport(handler)
    caplog.set_level(logging.DEBUG)
    assert confirm_email_link(TOKEN) == VERIFIED
    assert calls[0]["method"] == "POST"
    assert calls[0]["path"] == "/api/v1/auth/verification/confirm"
    assert calls[0]["params"] is None
    assert calls[0]["body"] == {"token": TOKEN}
    assert TOKEN not in calls[0]["path"]
    assert "authorization" not in {key.lower() for key in calls[0]["headers"]}
    assert TOKEN not in caplog.text


def test_confirm_callback_shows_api_errors_without_guessing(transport):
    def expired(_body):
        return 400, {"detail": EXPIRED}

    transport(expired)
    assert confirm_email_link(TOKEN) == EXPIRED

    def used(_body):
        return 400, {"detail": "This verification link was already used."}

    dash_api.install_transport_for_tests(lambda method, path, body, headers, params: used(body))
    assert confirm_email_link(TOKEN) == "This verification link was already used."

    def limited(_body):
        return 429, {"detail": LIMITED}

    dash_api.install_transport_for_tests(lambda method, path, body, headers, params: limited(body))
    assert confirm_email_link(TOKEN) == LIMITED
    assert confirm_email_link("") == "Open the verification link from your email."
    assert confirm_email_link(None) == "Open the verification link from your email."


def test_verify_boot_script_strips_the_fragment_and_does_not_log():
    page = app.server.test_client().get("/verify-email").get_data(as_text=True)
    assert "ajoCaptureVerifyToken" in page
    assert "replaceState" in page
    script = page.split("function ajoCaptureVerifyToken", 1)[1].split("function(hash, pathname)", 1)[0]
    assert "console.log" not in script
    assert "console.debug" not in script
    assert TOKEN not in page
    deps = json.dumps(app.server.test_client().get("/_dash-dependencies").get_json())
    assert "verify-token.data" in deps

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    token_js = json.dumps(TOKEN)
    program = (
        CAPTURE_VERIFY_TOKEN_JS
        + "\nconst loc = {pathname: '/verify-email', search: '', hash: '#' + "
        + token_js
        + ", state: null};\n"
        + "const hist = {state: null, url: '', replaceState(state, title, url) { this.url = url; loc.hash = ''; }};\n"
        + "const token = ajoCaptureVerifyToken(loc, hist);\n"
        + "if (token !== "
        + token_js
        + ") throw new Error('bare ' + token);\n"
        + "if (hist.url !== '/verify-email') throw new Error('url ' + hist.url);\n"
        + "if (hist.url.indexOf("
        + token_js
        + ") !== -1) throw new Error('token left in url');\n"
        + "const named = {pathname: '/verify-email/', search: '?from=email', hash: '#token=' + "
        + token_js
        + ", state: null};\n"
        + "const hist2 = {state: null, url: '', replaceState(state, title, url) { this.url = url; }};\n"
        + "const namedToken = ajoCaptureVerifyToken(named, hist2);\n"
        + "if (namedToken !== "
        + token_js
        + ") throw new Error('named ' + namedToken);\n"
        + "if (hist2.url !== '/verify-email/?from=email') throw new Error('named url ' + hist2.url);\n"
        + "const other = ajoCaptureVerifyToken({pathname: '/signin', search: '', hash: '#nope'}, {replaceState() { throw new Error('stripped other page'); }});\n"
        + "if (other !== '') throw new Error('other');\n"
    )
    ran = subprocess.run([node, "-e", program], capture_output=True, text=True, check=False)
    assert ran.returncode == 0, ran.stderr
