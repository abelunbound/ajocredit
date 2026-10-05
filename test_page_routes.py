"""Page addresses for refresh, back, and links.

Every screen has one path. Opening that path renders that screen. A member
who requests the admin payouts address is sent to the dashboard, including
when they type the URL instead of using a link. A signed-out visitor who
requests an app address is sent to sign-in.
"""

import json

import pytest
from flask import session

from app_dash_web import (
    PAGE_PATHS,
    app,
    gated_path,
    next_state,
    normalize_pathname,
    page_from_pathname,
    path_for_page,
    render_shell,
)
from stub_auth import APP_PAGES, AUTH_PAGES

ADMIN_PW = "pw-admin"
MEMBER_PW = "pw-member"

RENDER_OUTPUT = "..app-shell.children...signin-dock.style.."


def _canonical_output_id():
    matches = [
        key
        for key in app.callback_map
        if key.startswith("url.pathname@") and "signin-error" not in key
    ]
    assert len(matches) == 1, matches
    return matches[0]


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


def _render(client, pathname, auth_rev=1):
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
                {"id": "store-auth-rev", "property": "data", "value": auth_rev},
            ],
            "changedPropIds": ["url.pathname"],
            "state": [],
        },
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_data(as_text=True)


def _canonical(client, pathname):
    response = client.post(
        "/_dash-update-component",
        json={
            "output": _canonical_output_id(),
            "outputs": {"id": "url", "property": "pathname"},
            "inputs": [
                {"id": "url", "property": "pathname", "value": pathname},
                {"id": "store-auth-rev", "property": "data", "value": 1},
            ],
            "changedPropIds": ["url.pathname"],
            "state": [],
        },
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_json()
    return payload["response"]["url"]["pathname"]


class TestAddresses:
    def test_every_screen_has_one_address(self):
        assert set(PAGE_PATHS) == APP_PAGES | AUTH_PAGES
        assert len(set(PAGE_PATHS.values())) == len(PAGE_PATHS)

    def test_paths_round_trip(self):
        for page, path in PAGE_PATHS.items():
            assert page_from_pathname(path) == page
            assert path_for_page(page) == path
            assert normalize_pathname(path + "/") == path
            assert page_from_pathname(path + "?role=admin") == page
            if path != "/":
                assert page_from_pathname(path + "/") == page

    def test_unknown_address_is_not_a_page(self):
        assert page_from_pathname("/no-such-page") is None
        assert page_from_pathname("/payouts/../dashboard") is None


class TestDirectUrlAccess:
    @pytest.mark.parametrize(
        "path,needle",
        [
            ("/dashboard", "Good afternoon, Kemi."),
            ("/members", "usernames only"),
            ("/circle", "viewing as Tunde Exampleonly"),
            ("/credit", "Financial Health Overview"),
            ("/autoloan", "Interest-free safety net"),
            ("/wallet", "Available Early Payout"),
        ],
    )
    def test_member_refresh_renders_that_page(self, local_env, path, needle):
        client = _client("member", "membertest")
        response = client.get(path)
        assert response.status_code == 200
        assert response.request.path == path
        body = _render(client, path)
        assert needle in body
        assert "Release payout" not in body
        assert "Hold to release" not in body

    def test_admin_refresh_renders_payouts(self, local_env):
        client = _client("admin", "admintest")
        response = client.get("/payouts")
        assert response.status_code == 200
        body = _render(client, "/payouts")
        assert "Payouts Tracker" in body
        assert "Hold to release" in body

    def test_member_typed_payouts_url_is_redirected(self, local_env):
        client = _client("member", "membertest")
        response = client.get("/payouts")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")
        followed = client.get("/payouts", follow_redirects=True)
        assert followed.status_code == 200
        assert followed.request.path == "/dashboard"
        assert "Hold to release" not in followed.get_data(as_text=True)
        body = _render(client, "/payouts")
        assert "Hold to release" not in body
        assert "Release payout" not in body
        assert "Good afternoon, Kemi." in body
        assert _canonical(client, "/payouts") == "/dashboard"

    def test_non_creator_admin_typed_payouts_url_is_redirected(self, local_env):
        client = _client("admin", "not-the-creator")
        response = client.get("/payouts")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")
        body = _render(client, "/payouts")
        assert "Hold to release" not in body
        assert "Payouts Tracker" not in body
        assert 'href="/payouts"' not in body
        assert _canonical(client, "/payouts") == "/dashboard"

    def test_member_query_cannot_unlock_payouts(self, local_env):
        client = _client("member", "membertest")
        response = client.get("/payouts?role=admin")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")
        body = _render(client, "/payouts?role=admin")
        assert "Hold to release" not in body
        assert _canonical(client, "/payouts?role=admin") == "/dashboard"

    def test_trailing_slash_uses_the_canonical_address(self, local_env):
        client = _client("admin", "admintest")
        response = client.get("/payouts/")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/payouts")

    @pytest.mark.parametrize(
        "path",
        [
            "/dashboard",
            "/members",
            "/payouts",
            "/wallet",
            "/settings",
            "/settings/complete-profile",
            "/get-started/uk-check",
        ],
    )
    def test_signed_out_app_url_goes_to_signin(self, local_env, path):
        client = _client()
        response = client.get(path)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/signin")
        body = _render(client, path)
        payload = json.loads(body)
        assert payload["response"]["signin-dock"]["style"] == {}
        assert "Hold to release" not in body
        assert "Good afternoon, Kemi." not in body
        assert _canonical(client, path) == "/signin"

    def test_member_can_open_settings(self, local_env):
        client = _client("member", "membertest")
        response = client.get("/settings")
        assert response.status_code == 200
        assert response.request.path == "/settings"
        body = _render(client, "/settings")
        assert "Complete profile" in body
        assert "Hold to release" not in body

    def test_signed_out_can_open_landing_and_signin(self, local_env):
        client = _client()
        assert client.get("/").status_code == 200
        assert client.get("/signin").status_code == 200
        landing = json.loads(_render(client, "/"))
        signin = json.loads(_render(client, "/signin"))
        assert "Social capital" in json.dumps(landing)
        assert landing["response"]["signin-dock"]["style"].get("display") == "none"
        assert signin["response"]["signin-dock"]["style"] == {}
        assert "Social capital" not in json.dumps(signin["response"]["app-shell"])

    def test_unknown_address_returns_to_landing(self, local_env):
        client = _client()
        response = client.get("/no-such-page")
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/")

    def test_dash_internal_routes_are_not_redirected(self, local_env):
        client = _client()
        layout = client.get("/_dash-layout")
        deps = client.get("/_dash-dependencies")
        assert layout.status_code == 200
        assert deps.status_code == 200
        assert "url" in layout.get_data(as_text=True)


class TestLinksAndBack:
    def test_sidebar_links_match_the_role(self, local_env):
        with app.server.test_request_context():
            session["role"] = "member"
            session["username"] = "membertest"
            member = str(render_shell("home")).replace("'", '"')
            session["role"] = "admin"
            session["username"] = "admintest"
            admin = str(render_shell("payouts")).replace("'", '"')
        assert 'href="/dashboard"' in member
        assert 'href="/members"' in member
        assert 'href="/payouts"' not in member
        assert 'href="/payouts"' in admin
        assert "nav-btn on" in admin

    def test_back_renders_the_previous_address(self, local_env):
        client = _client("member", "membertest")
        history = ["/dashboard", "/members", "/credit"]
        seen = []
        for path in history:
            response = client.get(path)
            assert response.status_code == 200
            seen.append(_render(client, path))
        assert "Good afternoon, Kemi." in seen[0]
        assert "usernames only" in seen[1]
        assert "Financial Health Overview" in seen[2]
        # Browser back from credit to members, then to the dashboard.
        back_members = _render(client, history[-2])
        back_dashboard = _render(client, history[-3])
        assert "Financial Health Overview" not in back_members
        assert "usernames only" in back_members
        assert "Good afternoon, Kemi." in back_dashboard
        assert "Financial Health Overview" not in back_dashboard

    def test_admin_back_from_payouts_returns_to_members(self, local_env):
        client = _client("admin", "admintest")
        assert "usernames only" in _render(client, "/members")
        payouts = _render(client, "/payouts")
        assert "Hold to release" in payouts
        back = _render(client, "/members")
        assert "Hold to release" not in back
        assert "usernames only" in back

    def test_button_navigation_changes_the_address(self):
        with app.server.test_request_context():
            cases = [
                ({"type": "auth-btn", "action": "home-have-account"}, "landing", "/signin"),
                ({"type": "auth-btn", "action": "home-get-started"}, "landing", "/get-started"),
                ({"type": "auth-btn", "action": "getstarted-run-check"}, "getstarted-1", "/settings/complete-profile"),
                ({"type": "gs-timer", "screen": "2"}, "getstarted-2", "/settings/complete-profile"),
                ({"type": "auth-btn", "action": "dd-start-uk"}, "dd-overview", "/get-started/uk-check"),
                ({"type": "gs-timer", "screen": "uk"}, "getstarted-uk-loading", "/get-started/uk-result"),
                ({"type": "auth-btn", "action": "getstarted-finish"}, "getstarted-4", "/settings"),
                ({"type": "nav-btn", "page": "members"}, "home", "/members"),
                ({"type": "nav-btn", "page": "payouts"}, "home", "/dashboard"),
            ]
            session["role"] = "member"
            session["username"] = "membertest"
            for trigger, current, expected in cases:
                page, _rev, _error = next_state(trigger, current, 0, "", "")
                assert path_for_page(page) == expected

    def test_member_cannot_keep_payouts_after_navigating_back_to_it(self, local_env):
        client = _client("member", "membertest")
        with app.server.test_request_context():
            session["role"] = "member"
            session["username"] = "membertest"
            page, target = gated_path("/payouts", session.get("role"))
        assert page == "home"
        assert target == "/dashboard"
        assert "Hold to release" not in _render(client, "/payouts")
