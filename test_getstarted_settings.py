"""Registration, settings, and the UK-only due diligence path.

Nigeria stays locked. Stub sign-in remains the only way to set a server role.
"""

from pathlib import Path

import pytest
from flask import session

from app_dash_web import app, next_state, render_shell
from pages.getstarted import (
    SIGNUP_INCOMPLETE,
    due_diligence_layout,
    layout as registration_layout,
    nigeria_locked_step,
    signup_problem,
)
from pages.settings import apply_settings_action, layout as settings_layout
from stub_auth import APP_PAGES, AUTH_PAGES, gate_page

VALID_SIGNUP = {
    "first": "Ada",
    "last": "Okafor",
    "email": "ada@example.com",
    "phone": "07000000000",
    "password": "local-pass-1",
    "confirm": "local-pass-1",
}


def _signup(fields=None):
    return next_state(
        {"type": "auth-btn", "action": "signup-submit"},
        "getstarted-1",
        0,
        "",
        "",
        fields if fields is not None else VALID_SIGNUP,
    )


@pytest.fixture
def request_ctx():
    with app.server.test_request_context():
        session.clear()
        yield


SIGNUP_FIELDS = (
    ("signup-first-name", "First name"),
    ("signup-last-name", "Last name"),
    ("signup-email", "Email"),
    ("signup-phone", "Phone"),
    ("signup-password", "Set password"),
    ("signup-password-confirm", "Confirm password"),
)


def _nodes(component):
    found = []

    def walk(node):
        if node is None:
            return
        if isinstance(node, (list, tuple)):
            for item in node:
                walk(item)
            return
        data = node.to_plotly_json() if hasattr(node, "to_plotly_json") else node
        if not isinstance(data, dict):
            return
        found.append(data)
        walk((data.get("props") or {}).get("children"))

    walk(component)
    return found


class TestRegistration:
    def test_form_is_name_email_phone_and_password_only(self):
        text = str(registration_layout())
        for _field_id, label in SIGNUP_FIELDS:
            assert label in text
        assert "Country of origin" not in text
        assert "Nigeria" not in text
        assert "role-btn" not in text
        assert "signup-screen" in text
        assert "gs-screen" not in text

    def test_card_title_is_sign_up(self):
        titles = [
            (node.get("props") or {}).get("children")
            for node in _nodes(registration_layout())
            if "gs-title" in ((node.get("props") or {}).get("className") or "")
        ]
        assert titles == ["Sign Up"]
        assert "Registration" not in str(registration_layout())

    def test_fields_use_placeholders_without_labels_above(self):
        nodes = _nodes(registration_layout())
        assert not any("gs-label" in ((node.get("props") or {}).get("className") or "") for node in nodes)
        inputs = {
            (node.get("props") or {}).get("id"): node.get("props") or {}
            for node in nodes
            if (node.get("props") or {}).get("className") == "auth-input"
        }
        labels = [
            node.get("props") or {}
            for node in nodes
            if (node.get("props") or {}).get("className") == "visually-hidden"
        ]
        assert len(inputs) == len(SIGNUP_FIELDS)
        assert len(labels) == len(SIGNUP_FIELDS)
        for field_id, label in SIGNUP_FIELDS:
            assert inputs[field_id]["placeholder"] == label
            match = next(item for item in labels if item.get("htmlFor") == field_id)
            assert match["children"] == label
            assert match["aria-label"] == label
        css = Path("assets/dash_web.css").read_text(encoding="utf-8")
        assert ".signup-screen .auth-input .dash-input-element::placeholder{" in css
        assert "color:var(--ink-4);" in css

    def test_signup_card_matches_get_started_card_width(self):
        css = Path("assets/dash_web.css").read_text(encoding="utf-8")
        assert ".home-screen,\n.signup-screen{max-width:420px;}" in css
        assert ".home-screen .auth-primary-btn,\n.signup-screen .auth-input,\n.signup-screen .auth-primary-btn{\n  height:40px;\n}" in css

    def test_incomplete_form_stays_on_registration(self, request_ctx):
        page, _rev, error = _signup({"first": "Ada"})
        assert page == "getstarted-1"
        assert error == SIGNUP_INCOMPLETE
        assert "role" not in session

    def test_password_mismatch(self):
        fields = dict(VALID_SIGNUP)
        fields["confirm"] = "different-pass"
        assert signup_problem(fields) == "Passwords do not match."

    def test_valid_form_does_not_create_a_session_role(self, request_ctx):
        page, _rev, error = _signup()
        assert page == "signin"
        assert error == ""
        assert "role" not in session
        assert "username" not in session

    def test_get_started_opens_registration(self, request_ctx):
        page, _rev, error = next_state(
            {"type": "auth-btn", "action": "home-get-started"},
            "landing",
            0,
            "",
            "",
        )
        assert (page, error) == ("getstarted-1", "")
        page, _rev, error = next_state(
            {"type": "auth-btn", "action": "signin-get-started"},
            "signin",
            0,
            "",
            "",
        )
        assert (page, error) == ("getstarted-1", "")


class TestDueDiligenceOrder:
    def test_nigeria_step_is_locked_greyed_and_padlocked(self):
        step = str(nigeria_locked_step())
        assert "dd-step-locked" in step
        assert "bi-lock" in step
        assert "Checking your credit in Nigeria" in step
        assert "auth-btn" not in step
        css = Path("assets/dash_web.css").read_text(encoding="utf-8")
        assert "grayscale" in css
        assert ".dd-step-locked" in css

    def test_uk_is_the_default_path_before_nigeria(self):
        text = str(due_diligence_layout())
        uk = text.find("Check UK credit")
        nigeria = text.find("Checking your credit in Nigeria")
        assert 0 <= uk < nigeria
        assert "dd-start-uk" in text
        assert "getstarted-run-check" not in text

    def test_complete_profile_starts_uk_check_not_nigeria(self, request_ctx):
        session["username"] = "membertest"
        session["role"] = "member"
        page, _rev, _error = next_state(
            {"type": "auth-btn", "action": "settings-complete-profile"},
            "settings",
            1,
            "",
            "",
        )
        assert page == "dd-overview"
        page, _rev, _error = next_state(
            {"type": "auth-btn", "action": "dd-start-uk"},
            "dd-overview",
            1,
            "",
            "",
        )
        assert page == "getstarted-uk-loading"
        page, _rev, _error = next_state(
            {"type": "gs-timer", "screen": "uk"},
            "getstarted-uk-loading",
            1,
            "",
            "",
        )
        assert page == "getstarted-4"
        page, _rev, _error = next_state(
            {"type": "auth-btn", "action": "getstarted-finish"},
            "getstarted-4",
            1,
            "",
            "",
        )
        assert page == "settings"
        assert session["profile_uk_checked"] is True
        assert session["role"] == "member"

    def test_old_nigeria_trigger_does_not_run_before_uk(self, request_ctx):
        session["role"] = "member"
        session["username"] = "membertest"
        page, _rev, _error = next_state(
            {"type": "auth-btn", "action": "getstarted-run-check"},
            "getstarted-1",
            0,
            "",
            "",
        )
        assert page == "dd-overview"
        page, _rev, _error = next_state(
            {"type": "gs-timer", "screen": "2"},
            "getstarted-2",
            0,
            "",
            "",
        )
        assert page == "dd-overview"

    def test_profile_flow_requires_a_server_role(self, request_ctx):
        assert gate_page("settings", None) == "signin"
        assert gate_page("dd-overview", "member") == "dd-overview"
        assert "settings" in APP_PAGES
        assert "getstarted-1" in AUTH_PAGES
        assert "getstarted-2" not in AUTH_PAGES
        page, _rev, _error = next_state(
            {"type": "auth-btn", "action": "dd-start-uk"},
            "landing",
            0,
            "",
            "",
        )
        assert page == "signin"
        assert "role" not in session


class TestSettingsPage:
    def test_settings_includes_profile_actions(self):
        text = str(settings_layout("membertest", {}))
        for label in (
            "Complete profile",
            "Address Completion",
            "Verify phone number",
            "Reset password",
            "via email",
            "Set up direct debit",
        ):
            assert label in text
        assert "role-btn" not in text
        assert "store-role" not in text

    def test_sidebar_settings_keeps_fixed_role_label(self, request_ctx):
        session["username"] = "membertest"
        session["role"] = "member"
        text = str(render_shell("home", "admin")).replace("'", '"')
        assert 'href="/settings"' in text
        assert "Settings" in text
        assert "Member" in text
        assert "role-btn" not in text
        assert "Birmingham" not in text
        assert "PayoutsTracker" not in text

    def test_address_is_session_only_and_channels_are_not_sent(self):
        store = {}
        assert "Address saved" in apply_settings_action(
            "save-address",
            {"line": "1 High Street", "city": "Coventry", "postcode": "CV1 1AA"},
            store,
        )
        assert store["address_city"] == "Coventry"
        phone = apply_settings_action("verify-phone", {"phone": "07000000000"}, store)
        assert "No SMS was sent" in phone
        reset = apply_settings_action("reset-password", {}, store)
        assert "No email was sent" in reset
        debit = apply_settings_action("setup-direct-debit", {}, store)
        assert "not available" in debit
