"""Support Center page (#76).

Signed-in members and admins can open /support from the sidebar. The FAQ
holds placeholder answers. The contact form validates and confirms on
screen. It does not send email or SMS.
"""

import json

import pytest
from flask import session

from app_dash_web import PAGE_PATHS, app, render_page, render_shell
from pages.data import CRUMBS, NAV
from pages.support import FAQS, NO_EMAIL_SENT, SUPPORT_EMAIL, contact_reply, layout
from stub_auth import gate_page

ADMIN_PW = "pw-admin"
MEMBER_PW = "pw-member"

RENDER_OUTPUT = "..app-shell.children...signin-dock.style.."


def _write_credentials(path):
    path.write_text(
        json.dumps({"admintest": ADMIN_PW, "membertest": MEMBER_PW}),
        encoding="utf-8",
    )


@pytest.fixture
def local_env(tmp_path, monkeypatch):
    creds = tmp_path / "stub-users.json"
    _write_credentials(creds)
    monkeypatch.setenv("ALLOW_LOCAL_STUB_LOGIN", "true")
    monkeypatch.setenv("DASH_HOST", "127.0.0.1")
    monkeypatch.setenv("AJO_ENV", "local")
    monkeypatch.setenv("STUB_USERS_FILE", str(creds))
    return creds


def _client(role=None, username=None):
    client = app.server.test_client()
    if role is not None:
        with client.session_transaction() as sess:
            sess["role"] = role
            sess["username"] = username
    return client


def _render(client, pathname):
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


def _send(client, topic, subject, message, clicks=1):
    response = client.post(
        "/_dash-update-component",
        json={
            "output": "support-feedback.children",
            "outputs": {"id": "support-feedback", "property": "children"},
            "inputs": [{"id": "support-send", "property": "n_clicks", "value": clicks}],
            "changedPropIds": ["support-send.n_clicks"],
            "state": [
                {"id": "support-topic", "property": "value", "value": topic},
                {"id": "support-subject", "property": "value", "value": subject},
                {"id": "support-message", "property": "value", "value": message},
            ],
        },
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_data(as_text=True)


class TestSupportContent:
    def test_faq_lists_each_question_with_an_answer(self):
        text = str(layout())
        assert "Support Center" in text
        assert "Get help with your Ajo account and groups." in text
        assert "Frequently Asked Questions" in text
        assert len(FAQS) == 5
        for item in FAQS:
            assert item["question"] in text
            assert item["answer"] in text
            assert item["answer"].strip()
        assert "faq-item" in text
        assert "bi-chevron-down" in text

    def test_contact_form_matches_the_mock_options(self):
        text = str(layout())
        assert "Contact Support" in text
        assert "Topic" in text
        assert "Subject" in text
        assert "Message" in text
        assert "Send message" in text
        assert "Other Ways to Reach Us" in text
        assert f"Email: " in text
        assert SUPPORT_EMAIL in text
        assert "support-send" in text
        assert "mailto:" not in text

    def test_nav_and_address(self):
        labels = [label for _key, label, _icon in NAV]
        assert "Support" in labels
        assert PAGE_PATHS["support"] == "/support"
        assert CRUMBS["support"] == ["AjoFinance", "Support"]


class TestContactValidation:
    def test_incomplete_note_asks_for_the_missing_field(self):
        assert contact_reply("", "Hello", "Need help") == "Choose a topic."
        assert contact_reply("account", "  ", "Need help") == "Enter a subject."
        assert contact_reply("payout", "Payout date", "") == "Enter a message."
        assert contact_reply(None, None, None) == "Choose a topic."

    def test_complete_note_is_local_only(self):
        reply = contact_reply("safety", " Is my pot held? ", " Checking before I join. ")
        assert reply == NO_EMAIL_SENT
        assert "sent" in reply
        assert "@" not in reply


class TestAccess:
    def test_signed_out_support_url_goes_to_signin(self, local_env):
        assert gate_page("support", None) == "signin"
        client = _client()
        response = client.get("/support")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/signin")
        body = _render(client, "/support")
        assert "Support Center" not in body
        assert "support@ajo-platform.com" not in body

    @pytest.mark.parametrize(
        "role,username",
        [("member", "membertest"), ("admin", "admintest")],
    )
    def test_signed_in_roles_open_support_from_the_sidebar(self, local_env, role, username):
        assert gate_page("support", role) == "support"
        with app.server.test_request_context():
            session["role"] = role
            session["username"] = username
            shell = str(render_shell("support")).replace("'", '"')
        assert "Support Center" in shell
        assert 'href="/support"' in shell
        assert "nav-btn on" in shell
        assert "Other Ways to Reach Us" in shell
        client = _client(role, username)
        response = client.get("/support")
        assert response.status_code == 200
        assert response.request.path == "/support"
        body = _render(client, "/support")
        assert "What is Ajo and how does it work?" in body
        assert "How do I receive my payout?" in body
        page = render_page("support", role, username)
        assert "Frequently Asked Questions" in str(page)

    def test_send_confirms_without_email_for_a_signed_in_member(self, local_env):
        client = _client("member", "membertest")
        body = _send(client, "contribution", "April payment", "The dashboard still shows it due.")
        assert NO_EMAIL_SENT in body
        assert "smtp" not in body.lower()

    def test_send_rejects_a_blank_topic(self, local_env):
        client = _client("admin", "admintest")
        body = _send(client, "", "Hello", "Need a hand")
        assert "Choose a topic." in body
        assert NO_EMAIL_SENT not in body

    def test_signed_out_send_does_not_confirm(self, local_env):
        client = _client()
        body = _send(client, "account", "Hello", "Need a hand")
        assert NO_EMAIL_SENT not in body
        assert "Choose a topic." not in body
