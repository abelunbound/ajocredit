"""Role visibility for admintest and membertest.

Issue #23: each role may see Payouts Tracker only for Ajos it created, because
the creator is the default admin. This file checks:

* The signed-in Dash shell. ``admintest`` is the creator stub and sees
  Payouts Tracker. ``membertest`` does not. An admin session that is not the
  creator does not either.
* Typed addresses (#81, #91). ``/payouts`` renders the tracker only for the
  creator. A member, a non-creator admin, and a signed-out visitor are sent
  away before the tracker is rendered. ``/settings`` is an app address: both
  signed-in roles may open it, and a signed-out visitor is sent to sign-in.
* The persona fixture (#16). The single admin persona created both Ajos, so
  that persona is the only one the fixture grants Payouts Tracker for.
"""

import json
from pathlib import Path

import pytest
from flask import session

from app_dash_web import PAGE_PATHS, app, gated_path, next_state, render_shell
from pages.data import NAV
from pages.personas import EXAMPLE_PERSONAS_PATH, load_personas
from stub_auth import ADMIN_ONLY_PAGES, gate_page, nav_entries

ADMIN_PW = "pw-admin"
MEMBER_PW = "pw-member"

# Labels and headings the shell actually renders for both roles.
SHARED_NAV = (
    "Dashboard",
    "My Ajo",
    "Members",
    "FinHealth",
    "Delay Cover",
    "EarlyPayouts",
)
SHARED_PAGES = {
    "home": "Good afternoon, Kemi.",
    "circle": "Created by Amina Testperson",
    "members": "usernames only",
    "credit": "Credit & checks",
    "autoloan": "Delay Cover",
    "wallet": "Wallet",
}
# Strings that mark the admin payout surface. Shared copy such as
# "circles never miss a payout" is intentionally not in this list.
PAYOUTS_MARKERS = (
    "PayoutsTracker",
    "Hold to release",
    "Review & release",
    "Release payout",
    "Reschedule",
)
ADMIN_HOME_MARKERS = ("Release payout", "Review & release")
MEMBER_HOME_MARKER = "Pay this month"


def _write_credentials(path: Path):
    path.write_text(
        json.dumps({"admintest": ADMIN_PW, "membertest": MEMBER_PW}),
        encoding="utf-8",
    )


@pytest.fixture
def local_env(tmp_path, monkeypatch):
    path = tmp_path / "stub-users.json"
    _write_credentials(path)
    monkeypatch.setenv("ALLOW_LOCAL_STUB_LOGIN", "true")
    monkeypatch.setenv("DASH_HOST", "127.0.0.1")
    monkeypatch.setenv("AJO_ENV", "local")
    monkeypatch.setenv("STUB_USERS_FILE", str(path))
    return path


def _signin(username, password):
    return next_state(
        {"type": "auth-btn", "action": "signin-submit"},
        "signin",
        0,
        username,
        password,
    )


def _shell_after_signin(username, password, page):
    """Sign in, then render ``page``. The opposite role is passed as the client value and must be ignored."""
    page_name, _rev, error = _signin(username, password)
    assert page_name == "home"
    assert error == ""
    client_role = "member" if username == "admintest" else "admin"
    return str(render_shell(page, client_role))


def _dash_render(client, pathname):
    """Render the shell for a typed address. The page store is not the route."""
    response = client.post(
        "/_dash-update-component",
        json={
            "output": "..app-shell.children...signin-dock.style..",
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


def _session_client(role=None, username=None):
    client = app.server.test_client()
    if role is not None:
        with client.session_transaction() as sess:
            sess["role"] = role
            sess["username"] = username
    return client


def ajos_with_payouts_tracker(document, persona):
    """Ajos whose Payouts Tracker this persona may see: only groups it created."""
    return [
        group["name"]
        for group in document["groups"]
        if group["created_by"] == persona["id"]
    ]


class TestPersonaCreatorRule:
    """The #16 fixture is the source of 'created this Ajo, so default admin'."""

    def test_only_the_creator_is_granted_payouts_tracker(self):
        document = load_personas(EXAMPLE_PERSONAS_PATH)
        creators = {group["created_by"] for group in document["groups"]}

        for persona in document["personas"]:
            visible = ajos_with_payouts_tracker(document, persona)
            membership = set(persona["groups"])
            if persona["role"] == "admin":
                assert persona["id"] in creators
                assert visible == ["Brum Builders", "Sister Circle Ajo"]
                assert set(visible) == membership
            else:
                assert persona["id"] not in creators
                assert visible == []
                assert membership
                assert set(visible).isdisjoint(membership)

    def test_a_member_of_one_group_still_does_not_see_its_tracker(self):
        document = load_personas(EXAMPLE_PERSONAS_PATH)
        single_group = [
            persona for persona in document["personas"] if len(persona["groups"]) == 1
        ]
        assert len(single_group) == 5
        for persona in single_group:
            assert persona["role"] == "member"
            assert ajos_with_payouts_tracker(document, persona) == []


class TestShellVisibility:
    @pytest.mark.parametrize("username,password,role_label", [
        ("admintest", ADMIN_PW, "Admin"),
        ("membertest", MEMBER_PW, "Member"),
    ])
    def test_shared_navigation_is_visible_to_both_roles(self, local_env, username, password, role_label):
        with app.server.test_request_context():
            text = _shell_after_signin(username, password, "home")
            for label in SHARED_NAV:
                assert label in text
            assert role_label in text
            assert "role-btn" not in text
            assert "Brum Builders" in text
            assert 'href="/settings"' in text.replace("'", '"')

    def test_admin_sees_payouts_tracker_and_release_actions(self, local_env):
        with app.server.test_request_context():
            home = _shell_after_signin("admintest", ADMIN_PW, "home")
            assert "PayoutsTracker" in home
            for marker in ADMIN_HOME_MARKERS:
                assert marker in home
            assert "@admintest" in home
            assert session["role"] == "admin"

            payouts = str(render_shell("payouts", "member"))
            assert "PayoutsTracker" in payouts
            assert "Payouts Tracker" in payouts
            assert "Hold to release" in payouts
            assert "Reschedule" in payouts
            assert "Rotation queue" in payouts

    def test_member_does_not_see_payouts_tracker_or_release_actions(self, local_env):
        with app.server.test_request_context():
            home = _shell_after_signin("membertest", MEMBER_PW, "home")
            for marker in PAYOUTS_MARKERS:
                assert marker not in home
            assert MEMBER_HOME_MARKER in home
            assert "@membertest" in home
            assert session["role"] == "member"

            labels = [label for _key, label, _icon in nav_entries(NAV, session["role"])]
            assert "PayoutsTracker" not in labels

    @pytest.mark.parametrize("page,marker", list(SHARED_PAGES.items()))
    def test_member_can_open_shared_pages(self, local_env, page, marker):
        with app.server.test_request_context():
            text = _shell_after_signin("membertest", MEMBER_PW, page)
            assert marker in text
            assert "PayoutsTracker" not in text
            assert "Hold to release" not in text
            assert gate_page(page, session["role"]) == page

    @pytest.mark.parametrize("page,marker", list(SHARED_PAGES.items()))
    def test_admin_can_open_shared_pages(self, local_env, page, marker):
        with app.server.test_request_context():
            text = _shell_after_signin("admintest", ADMIN_PW, page)
            assert marker in text
            assert "PayoutsTracker" in text
            assert gate_page(page, session["role"]) == page


class TestDirectAccess:
    """Each screen has an address. ``/payouts`` is creator-gated; ``/settings`` is signed-in."""

    def test_screens_have_addresses(self):
        assert PAGE_PATHS["payouts"] == "/payouts"
        assert PAGE_PATHS["settings"] == "/settings"
        assert PAGE_PATHS["home"] == "/dashboard"

    def test_creator_typed_payouts_url_shows_the_tracker(self, local_env):
        client = _session_client("admin", "admintest")
        response = client.get("/payouts")
        assert response.status_code == 200
        assert response.request.path == "/payouts"
        body = _dash_render(client, "/payouts")
        assert "PayoutsTracker" in body
        assert "Hold to release" in body
        assert "Brum Builders" in body
        assert "Sister Circle Ajo" in body

    def test_member_typed_payouts_url_is_sent_to_the_dashboard(self, local_env):
        client = _session_client("member", "membertest")
        response = client.get("/payouts")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")
        body = _dash_render(client, "/payouts")
        assert "Hold to release" not in body
        assert "PayoutsTracker" not in body
        assert "Release payout" not in body
        assert "Good afternoon, Kemi." in body
        with app.server.test_request_context():
            session["role"] = "member"
            session["username"] = "membertest"
            page, target = gated_path("/payouts", "member")
        assert page == "home"
        assert target == "/dashboard"

    def test_non_creator_admin_typed_payouts_url_is_sent_to_the_dashboard(self, local_env):
        client = _session_client("admin", "not-the-creator")
        response = client.get("/payouts")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")
        body = _dash_render(client, "/payouts")
        assert "Hold to release" not in body
        assert "PayoutsTracker" not in body
        with app.server.test_request_context():
            session["role"] = "admin"
            session["username"] = "not-the-creator"
            text = str(render_shell("payouts", "admin"))
            assert "Hold to release" not in text
            assert "PayoutsTracker" not in text

    def test_query_string_cannot_unlock_payouts_for_a_member(self, local_env):
        client = _session_client("member", "membertest")
        response = client.get("/payouts?role=admin")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")
        body = _dash_render(client, "/payouts?role=admin")
        assert "Hold to release" not in body

    def test_unknown_payouts_path_does_not_render_the_tracker(self, local_env):
        client = _session_client("member", "membertest")
        response = client.get("/payouts/brum-builders")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/")
        body = _dash_render(client, "/payouts/brum-builders")
        assert "Hold to release" not in body

    @pytest.mark.parametrize("path", ["/payouts", "/settings"])
    def test_signed_out_app_addresses_go_to_signin(self, local_env, path):
        client = _session_client()
        response = client.get(path)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/signin")
        body = _dash_render(client, path)
        payload = json.loads(body)
        shell = json.dumps(payload["response"]["app-shell"])
        assert payload["response"]["signin-dock"]["style"] == {}
        assert "Hold to release" not in shell
        assert "PayoutsTracker" not in shell
        assert "Complete profile" not in shell

    @pytest.mark.parametrize("role,username", [("admin", "admintest"), ("member", "membertest")])
    def test_signed_in_roles_can_open_settings(self, local_env, role, username):
        client = _session_client(role, username)
        response = client.get("/settings")
        assert response.status_code == 200
        assert response.request.path == "/settings"
        body = _dash_render(client, "/settings")
        assert "Complete profile" in body
        assert "Hold to release" not in body
        with app.server.test_request_context():
            session["role"] = role
            session["username"] = username
            assert gated_path("/settings", role) == ("settings", "/settings")

    def test_member_nav_click_cannot_open_payouts(self, local_env):
        with app.server.test_request_context():
            _signin("membertest", MEMBER_PW)
            page, _rev, _error = next_state(
                {"type": "nav-btn", "page": "payouts"},
                "home",
                1,
                "",
                "",
            )
            assert page == "home"
            assert "payouts" in ADMIN_ONLY_PAGES
            assert gate_page("payouts", "member") == "home"

    def test_client_role_value_cannot_reveal_payouts_to_a_member(self, local_env):
        with app.server.test_request_context():
            _signin("membertest", MEMBER_PW)
            text = str(render_shell("payouts", "admin"))
            assert session["role"] == "member"
            assert "PayoutsTracker" not in text
            assert "Hold to release" not in text
