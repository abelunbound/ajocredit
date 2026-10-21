"""Financial Health Overview (issue #28).

The FinHealth page is renamed, the country-of-origin card is locked, and the
affordability assessment and forecast cards are present for both roles.
"""

import pytest
from flask import session

from app_dash_web import app as dash_app
from app_dash_web import render_page, render_shell
from pages.credit import (
    APPLICANT_BALANCE,
    BUFFER,
    FORECAST_DAY30,
    PAGE_TITLE,
    TUITION,
    assessment_chart,
    forecast_chart,
    forecast_series,
    layout,
)
from pages.data import CRUMBS


@pytest.fixture
def app():
    return dash_app


def test_page_title_and_crumb():
    text = str(layout())
    assert PAGE_TITLE in text
    assert "Credit & checks" not in text
    assert CRUMBS["credit"][-1] == PAGE_TITLE


def test_origin_card_is_locked():
    text = str(layout())
    assert "Check A · Country of origin" in text
    assert "Country of origin check is locked" in text
    assert "aria-disabled" in text
    assert "cr-locked" in text
    assert "Locked" in text


def test_affordability_cards_match_the_brief():
    text = str(layout())
    assert "Affordability Assessment" in text
    assert "Tuition & Living Expenses (£)" in text
    assert "£14000" in text
    assert f"£{APPLICANT_BALANCE}" in text
    assert "Threshold met" in text
    assert "Cross-border debt/liability" in text
    assert "£0" in text
    assert "Financial History (£) – 12 Months" in text
    assert "Volatility check - 7-Day rolling standard deviation" in text

    assert "Affordability Forecast" in text
    assert "£14000.00" in text
    assert f"£{FORECAST_DAY30}.00" in text
    assert f"£{BUFFER}.00" in text
    assert "50-90%" in text
    assert "Next 30 days Forecast (£)" in text
    assert "Forecast vs Validation data (£)" in text


def test_chart_views_switch():
    history = str(assessment_chart("history"))
    volatility = str(assessment_chart("volatility"))
    forecast = str(forecast_chart("forecast"))
    validation = str(forecast_chart("validation"))
    assert "Daily bank balance" in history
    assert "Last 3 Months" in history
    assert "7-day rolling standard deviation" in volatility
    assert "Daily bank balance" not in volatility
    assert "Forecasted balance" in forecast
    assert "Forecast versus validation" in validation
    assert "Validation data" in validation


def test_forecast_buffer_matches_day_30():
    assert forecast_series()[-1] == FORECAST_DAY30
    assert BUFFER == FORECAST_DAY30 - TUITION
    assert BUFFER == 3950


@pytest.mark.parametrize("role", ["member", "admin"])
def test_finhealth_renders_for_both_roles(app, role):
    username = "admintest" if role == "admin" else "membertest"
    with app.server.test_request_context():
        session.clear()
        session["username"] = username
        session["role"] = role
        page = render_page("credit", role)
        shell = render_shell("credit", role)
    assert PAGE_TITLE in str(page)
    assert PAGE_TITLE in str(shell)
    assert "PayoutsTracker" in str(shell) if role == "admin" else "PayoutsTracker" not in str(shell)
