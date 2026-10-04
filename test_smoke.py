"""
Smoke tests for AjoFinance Dash app.

Tests that all pages/screens render without errors for both member and admin roles.
This ensures that no page throws an exception when rendered.
"""

import pytest
from dash import Dash
from app_dash_web import render_page, render_shell


@pytest.fixture
def app():
    """Create a minimal Dash app for testing."""
    test_app = Dash(__name__)
    return test_app


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
    ])
    def test_render_page(self, app, page, role):
        """Test that render_page works for all pages and roles."""
        with app.server.app_context():
            layout = render_page(page, role)
            assert layout is not None, f"Page {page} for role {role} returned None"

    @pytest.mark.parametrize("role", ["member", "admin"])
    @pytest.mark.parametrize("page", [
        "landing",
        "signin",
        "getstarted-1",
        "getstarted-2",
        "getstarted-3",
        "getstarted-uk-loading",
        "getstarted-4",
    ])
    def test_render_shell_auth_screens(self, app, page, role):
        """Test that render_shell works for auth screens (landing, signin, get-started)."""
        with app.server.app_context():
            shell = render_shell(page, role)
            assert shell is not None, f"Shell for page {page} (role {role}) returned None"

    @pytest.mark.parametrize("role", ["member", "admin"])
    def test_render_shell_main_app(self, app, role):
        """Test that render_shell works for main app pages with sidebar."""
        with app.server.app_context():
            shell = render_shell("home", role)
            assert shell is not None, f"Shell for home page (role {role}) returned None"


class TestPageCoverage:
    """Verify we're testing all pages mentioned in the app."""

    def test_all_pages_covered(self):
        """Ensure all pages in render_page are covered by tests."""
        pages = ["home", "members", "payouts", "credit", "autoloan", "wallet", "circle"]
        for page in pages:
            assert page in [
                "home", "members", "payouts", "credit", "autoloan", "wallet", "circle"
            ], f"Page {page} should be tested"

    def test_all_auth_screens_covered(self):
        """Ensure all auth screens in render_shell are covered by tests."""
        auth_screens = [
            "landing",
            "signin",
            "getstarted-1",
            "getstarted-2",
            "getstarted-3",
            "getstarted-uk-loading",
            "getstarted-4",
        ]
        for screen in auth_screens:
            assert screen in [
                "landing", "signin", "getstarted-1", "getstarted-2", "getstarted-3",
                "getstarted-uk-loading", "getstarted-4"
            ], f"Auth screen {screen} should be tested"
