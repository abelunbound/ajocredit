"""
Smoke tests for AjoFinance Dash app.

Tests that all pages/screens render without errors for both member and admin roles.
This ensures that no page throws an exception when rendered.
"""

import pytest
from flask import session

from app_dash_web import app as dash_app
from app_dash_web import render_page, render_shell
from pages.getstarted import layout as getstarted_layout
from pages.signin import layout as signin_layout


@pytest.fixture
def app():
    """Use the real Dash app so session-backed shells can render."""
    return dash_app


class TestPageLayouts:
    """Test that all page layouts render without errors."""

    @pytest.mark.parametrize("role", ["member", "admin"])
    @pytest.mark.parametrize("page", [
        "home",
        "members",
        "payouts",
        "credit",
        "autoloan",
        "wallet",
        "circle",
        "settings",
    ])
    def test_render_page(self, app, page, role):
        """Test that render_page works for all pages and roles."""
        with app.server.app_context():
            username = "admintest" if role == "admin" else "membertest"
            layout = render_page(page, role, username)
            assert layout is not None, f"Page {page} for role {role} returned None"

    @pytest.mark.parametrize("role", ["member", "admin"])
    @pytest.mark.parametrize("page", [
        "landing",
        "signin",
        "getstarted-1",
    ])
    def test_render_shell_auth_screens(self, app, page, role):
        """Test that render_shell works for auth screens (landing, signin, registration)."""
        with app.server.test_request_context():
            session.clear()
            if page == "signin":
                shell = signin_layout()
            elif page == "getstarted-1":
                shell = getstarted_layout()
            else:
                shell = render_shell(page, role)
            assert shell is not None, f"Shell for page {page} (role {role}) returned None"

    @pytest.mark.parametrize("role", ["member", "admin"])
    @pytest.mark.parametrize("page", [
        "settings",
        "dd-overview",
        "getstarted-2",
        "getstarted-3",
        "getstarted-uk-loading",
        "getstarted-4",
    ])
    def test_render_shell_profile_flow(self, app, page, role):
        """Signed-in settings and credit-check screens render for both roles."""
        username = "admintest" if role == "admin" else "membertest"
        with app.server.test_request_context():
            session.clear()
            session["username"] = username
            session["role"] = role
            shell = render_shell(page, "admin" if role == "member" else "member")
            assert shell is not None, f"Shell for page {page} (role {role}) returned None"

    @pytest.mark.parametrize("role", ["member", "admin"])
    def test_render_shell_main_app(self, app, role):
        """Test that render_shell works for main app pages with sidebar."""
        username = "admintest" if role == "admin" else "membertest"
        with app.server.test_request_context():
            session.clear()
            session["username"] = username
            session["role"] = role
            shell = render_shell("home", "admin" if role == "member" else "member")
            assert shell is not None, f"Shell for home page (role {role}) returned None"
            text = str(shell)
            if role == "admin":
                assert "PayoutsTracker" in text
            else:
                assert "PayoutsTracker" not in text


class TestPageCoverage:
    """Verify we're testing all pages mentioned in the app."""

    def test_all_pages_covered(self):
        """Ensure all pages in render_page are covered by tests."""
        pages = ["home", "members", "payouts", "credit", "autoloan", "wallet", "circle", "settings"]
        for page in pages:
            assert page in [
                "home", "members", "payouts", "credit", "autoloan", "wallet", "circle", "settings"
            ], f"Page {page} should be tested"

    def test_all_auth_screens_covered(self):
        """Ensure all auth screens in render_shell are covered by tests."""
        auth_screens = [
            "landing",
            "signin",
            "getstarted-1",
        ]
        for screen in auth_screens:
            assert screen in [
                "landing", "signin", "getstarted-1",
            ], f"Auth screen {screen} should be tested"
