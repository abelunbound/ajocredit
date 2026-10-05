"""Dashboard home (#17): no rotation calendar, no hidden-bank note, compact recipient."""

import re
from pathlib import Path

import pytest

from pages.dashboard import layout as dashboard_layout

CSS_PATH = Path(__file__).resolve().parent / "assets" / "dash_web.css"


def _flat(node):
    return str(node)


def _css_block(selector):
    css = CSS_PATH.read_text(encoding="utf-8")
    for match in re.finditer(r"([^{}]+)\{([^}]*)\}", css):
        selectors = [part.strip() for part in match.group(1).split(",")]
        if selector in selectors:
            return match.group(2)
    raise AssertionError(f"Missing CSS rule {selector}")


@pytest.mark.parametrize("role", ["member", "admin"])
def test_calendar_and_hidden_bank_removed(role):
    text = _flat(dashboard_layout(role))
    assert "Rotation · 10 months" not in text
    assert "cal-grid" not in text
    assert "Bank details hidden" not in text
    assert "row-note" not in text
    assert "Next recipient" in text
    assert "@abel_o" in text
    assert "Abel O. · Apr 28" in text
    assert "£5,000" in text
    assert "No bank details shared" in text
    assert "Recent activity" in text
    assert "Circle safety" in text


def test_role_actions_stay_on_dashboard():
    member = _flat(dashboard_layout("member"))
    admin = _flat(dashboard_layout("admin"))
    assert "Pay this month" in member
    assert "Release payout" not in member
    assert "Release payout" in admin
    assert "Review & release" in admin


def test_recipient_section_is_smaller_than_legacy_sizes():
    text = _flat(dashboard_layout("member"))
    assert "dash-who" in text
    assert "dash-amt" in text
    assert "nr-amt" not in text
    assert "nr-av" not in text

    amt = _css_block(".dash-amt")
    av = _css_block(".dash-av")
    handle = _css_block(".dash-handle")
    row = _css_block(".dash-who-row")

    amt_size = int(re.search(r"font-size:(\d+)px", amt).group(1))
    av_size = int(re.search(r"width:(\d+)px", av).group(1))
    handle_size = int(re.search(r"font-size:(\d+)px", handle).group(1))
    gap = int(re.search(r"gap:(\d+)px", row).group(1))

    # Legacy next-recipient amount was 40px and the avatar was 44px.
    assert amt_size <= 22
    assert av_size <= 28
    assert handle_size <= 13
    assert gap >= 24


def test_second_row_cards_share_height():
    text = _flat(dashboard_layout("member"))
    assert "dash-row-2" in text
    assert text.count("dash-equal") == 3

    row = _css_block(".dash-row").replace(" ", "")
    side = _css_block(".dash-side").replace(" ", "")
    assert "align-items:stretch" in row
    assert "grid-template-rows:1fr1fr" in side
