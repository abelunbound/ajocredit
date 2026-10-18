"""Dashboard home (#17, #102): no rotation calendar, dummy bank-card ad on the right."""

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
    assert "Next recipient" not in text
    assert "AjoCard" in text
    assert "Payouts on your card" in text
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


def test_right_card_is_dummy_bank_ad():
    text = _flat(dashboard_layout("member"))
    assert "dash-ad" in text
    assert "dash-bank-card" in text
    assert "Sponsored" in text
    assert "Payouts on your card" in text
    assert "dummy prepaid debit" not in text
    assert "dash-who" not in text
    assert "nr-amt" not in text
    assert "nr-av" not in text
    card = _css_block(".dash-bank-card")
    assert "linear-gradient" in card


def test_second_row_cards_share_height():
    text = _flat(dashboard_layout("member"))
    assert "dash-row-2" in text
    assert text.count("dash-equal") == 3

    row = _css_block(".dash-row").replace(" ", "")
    side = _css_block(".dash-side").replace(" ", "")
    assert "align-items:stretch" in row
    assert "grid-template-rows:1fr1fr" in side
