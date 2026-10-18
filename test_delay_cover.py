"""Delay Cover rename and the Request Cover popup flow."""

from app_dash_web import app, render_page, render_shell
from flask import session

from pages.delay_cover import (
    AJO_GROUPS,
    COVER_MONTHS,
    handle_delay_cover,
    initial_state,
    payback_options,
    reduce_request,
)


def _page_text(page, role, username=None):
    with app.server.app_context():
        return str(render_page(page, role, username))


def _walk(actions):
    state = initial_state()
    error = ""
    month = group = repay = ""
    for action, updates in actions:
        month = updates.get("month", month)
        group = updates.get("group", group)
        repay = updates.get("repay", repay)
        state, error = reduce_request(state, action, month, group, repay)
    return state, error


class TestDelayCoverCopy:
    def test_page_uses_delay_cover_name(self):
        text = _page_text("autoloan", "member")
        assert "Delay Cover" in text
        assert "Request Cover" in text
        assert "Active on 1 circle" in text
        assert "Auto-loan" not in text
        assert "Autoloan" not in text

    def test_popup_offers_month_group_and_payback(self):
        text = _page_text("autoloan", "admin")
        assert "Which month?" in text
        assert "Which Ajo?" in text
        assert "When can you pay it back?" in text
        for month in COVER_MONTHS:
            assert month in text
        for group in AJO_GROUPS:
            assert group in text

    def test_other_screens_use_delay_cover_name(self):
        assert "Auto-loan" not in _page_text("home", "member", "membertest")
        assert "Auto-loan" not in _page_text("circle", "member", "membertest")
        tracker = _page_text("payouts", "admin", "admintest")
        assert "Auto-loan" not in tracker
        assert "Delay Cover cover" in tracker
        hidden = _page_text("payouts", "admin", "not-the-creator")
        assert "Hold to release" not in hidden

    def test_breadcrumb_and_nav_label(self):
        with app.server.test_request_context():
            session.clear()
            session["username"] = "membertest"
            session["role"] = "member"
            text = str(render_shell("autoloan", None))
        assert "Delay Cover" in text
        assert "Auto-loan" not in text


class TestRequestFlow:
    def test_payback_is_after_cover_month(self):
        assert payback_options("May 2026")[0] == "Jun 2026"
        assert "May 2026" not in payback_options("May 2026")
        assert payback_options("Nov 2026") == ("Dec 2026", "Jan 2027", "Feb 2027")
        assert payback_options("not-a-month") == ()

    def test_each_step_requires_a_choice(self):
        state, error = _walk([("open", {}), ("next", {})])
        assert state["step"] == "month"
        assert "month" in error

        state, error = _walk([("open", {}), ("next", {"month": "May 2026"}), ("next", {})])
        assert state["step"] == "group"
        assert "Ajo" in error

        state, error = _walk(
            [
                ("open", {}),
                ("next", {"month": "May 2026"}),
                ("next", {"group": "Brum Builders"}),
                ("next", {"repay": "May 2026"}),
            ]
        )
        assert state["step"] == "repay"
        assert "payback" in error

    def test_full_request_notes_the_choice_without_granting_cover(self):
        state, error = _walk(
            [
                ("open", {}),
                ("next", {"month": "Aug 2026"}),
                ("next", {"group": "Sister Circle Ajo"}),
                ("next", {"repay": "Oct 2026"}),
                ("submit", {}),
            ]
        )
        assert error == ""
        assert state["open"] is True
        assert state["step"] == "done"
        assert state["month"] == "Aug 2026"
        assert state["group"] == "Sister Circle Ajo"
        assert state["repay"] == "Oct 2026"

    def test_back_and_close(self):
        state, error = _walk(
            [
                ("open", {}),
                ("next", {"month": "Jun 2026"}),
                ("back", {}),
            ]
        )
        assert error == ""
        assert state["step"] == "month"
        assert state["month"] == "Jun 2026"

        state, error = reduce_request(state, "close", "Jun 2026", "", "")
        assert state == initial_state()
        assert error == ""

    def test_changing_cover_month_drops_an_earlier_payback(self):
        state, _error = _walk(
            [
                ("open", {}),
                ("next", {"month": "May 2026"}),
                ("next", {"group": "Brum Builders"}),
                ("next", {"repay": "Jun 2026"}),
                ("back", {}),
                ("back", {}),
                ("back", {}),
            ]
        )
        assert state["step"] == "month"
        state, error = reduce_request(state, "next", "Nov 2026", "Brum Builders", "Jun 2026")
        assert error == ""
        assert state["repay"] == ""
        assert state["step"] == "group"

    def test_callback_opens_the_dialog(self):
        (
            modal,
            month,
            group,
            repay,
            review,
            done,
            back,
            nxt,
            submit,
            error,
            summary,
            done_summary,
            repay_options,
            repay_value,
            store,
        ) = handle_delay_cover("dc-open", initial_state(), "", "", "")
        assert modal["display"] == "flex"
        assert month == {}
        assert group["display"] == "none"
        assert repay["display"] == "none"
        assert review["display"] == "none"
        assert done["display"] == "none"
        assert back["display"] == "none"
        assert nxt == {}
        assert submit["display"] == "none"
        assert error == ""
        assert summary == ""
        assert done_summary == ""
        assert repay_value == ""
        assert any(item["value"] == "Jun 2026" for item in repay_options)
        assert store["open"] is True
        registered = str(app.callback_map)
        assert "dc-open" in registered
        assert "dc-modal" in registered
