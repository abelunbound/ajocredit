"""Payouts Tracker is visible only to the creator of that Ajo.

The #20 gate stays: members are redirected server-side, and there is no role toggle.
"""

import json

from flask import session

from app_dash_web import app, next_state, render_page, render_shell
from pages.payout_access import resolve_ajo, visible_ajo_names
from pages.payouts import layout as payouts_layout
from pages.payouts import tracker_body
from pages.personas import EXAMPLE_PERSONAS_PATH
from stub_auth import gate_page


def _document():
    return json.loads(EXAMPLE_PERSONAS_PATH.read_text(encoding="utf-8"))


def _shell(page, role, username):
    with app.server.test_request_context():
        session.clear()
        session["role"] = role
        session["username"] = username
        return str(render_shell(page, "admin" if role == "member" else "member"))


def test_creator_sees_only_ajos_they_created():
    document = _document()
    document["groups"][1]["created_by"] = "persona-02"
    document["groups"].append({"name": "Other Hands Ajo", "created_by": "persona-06"})

    names = visible_ajo_names("admintest", "admin", document)

    assert names == ["Brum Builders"]
    assert resolve_ajo("Sister Circle Ajo", "admintest", "admin", document) == "Brum Builders"
    assert resolve_ajo("Other Hands Ajo", "admintest", "admin", document) == "Brum Builders"
    assert resolve_ajo("Brum Builders", "admintest", "admin", document) == "Brum Builders"


def test_member_and_non_creator_see_no_tracker():
    document = _document()

    assert visible_ajo_names("membertest", "member", document) == []
    assert visible_ajo_names("admintest", "member", document) == []
    assert visible_ajo_names("membertest", "admin", document) == []
    assert visible_ajo_names("not-the-creator", "admin", document) == []
    assert resolve_ajo("Brum Builders", "membertest", "member", document) is None
    assert gate_page("payouts", "member") == "home"


def test_default_fixture_creator_sees_both_recorded_ajos():
    names = visible_ajo_names("admintest", "admin", _document())

    assert names == ["Brum Builders", "Sister Circle Ajo"]


def test_tracker_body_does_not_mix_ajo_rows():
    brum, _side = tracker_body("Brum Builders", "kemi_a", "admin")
    sister, _sister_side = tracker_body("Sister Circle Ajo", "kemi_a", "admin")
    other, _other_side = tracker_body("Other Hands Ajo", "kemi_a", "admin")
    brum_text = str(brum)
    sister_text = str(sister)

    assert "Rotation queue · Brum Builders" in brum_text
    assert "AJO-BBM-01-0228" in brum_text
    assert "AJO-SCA-01-0312" not in brum_text
    assert "@amina_t" not in brum_text
    assert "Rotation queue · Sister Circle Ajo" in sister_text
    assert "AJO-SCA-01-0312" in sister_text
    assert "AJO-BBM-01-0228" not in sister_text
    assert "@kemi_a" not in sister_text
    assert "Hold to release £2,000" in str(_sister_side)
    other_text = str(other)
    assert "Other Hands Ajo" in other_text
    assert "@kemi_a" not in other_text
    assert "Hold to release" not in other_text


def test_creator_shell_shows_tracker_for_created_ajos():
    text = _shell("payouts", "admin", "admintest")

    assert "PayoutsTracker" in text
    assert "Payouts Tracker" in text
    assert "Brum Builders" in text
    assert "Sister Circle Ajo" in text
    assert "only the creator of this Ajo can see this tracker" in text
    assert "Hold to release £5,000" in text
    assert "AJO-BBM-01-0228" in text
    assert "AJO-SCA-01-0312" not in text
    assert "role-btn" not in text
    assert "store-role" not in text


def test_member_is_redirected_and_cannot_see_tracker_text():
    text = _shell("payouts", "member", "membertest")

    assert "PayoutsTracker" not in text
    assert "Payouts Tracker" not in text
    assert "Hold to release" not in text
    assert "only the creator of this Ajo" not in text
    assert "AJO-BBM-01-0228" not in text
    assert "role-btn" not in text
    assert "@membertest" in text


def test_admin_who_is_not_the_creator_is_redirected():
    text = _shell("payouts", "admin", "not-the-creator")

    assert "PayoutsTracker" not in text
    assert "Hold to release" not in text
    assert "only the creator of this Ajo" not in text
    with app.server.test_request_context():
        session["role"] = "admin"
        session["username"] = "not-the-creator"
        page, _rev, _error = next_state(
            {"type": "nav-btn", "page": "payouts"},
            "home",
            1,
            "",
            "",
        )
        assert page == "home"
        denied = str(render_page("payouts", "admin", "not-the-creator"))
        assert "Hold to release" not in denied
        assert "Payouts Tracker" not in denied


def test_member_nav_request_stays_on_home():
    with app.server.test_request_context():
        session["role"] = "member"
        session["username"] = "membertest"
        page, _rev, _error = next_state(
            {"type": "nav-btn", "page": "payouts"},
            "home",
            1,
            "",
            "",
        )
        assert page == "home"
        assert gate_page("payouts", "member") == "home"


def test_layout_for_member_has_no_tracker_controls():
    text = str(payouts_layout("member", "membertest"))

    assert "payouts-tracker-denied" in text
    assert "Hold to release" not in text
    assert "payout-ajo-btn" not in text
    assert "role-btn" not in text


def _post_tracker(role, username, ajo_name):
    client = app.server.test_client()
    with client.session_transaction() as sess:
        sess["role"] = role
        sess["username"] = username
    names = ["Brum Builders", "Sister Circle Ajo"]
    response = client.post(
        "/_dash-update-component",
        json={
            "output": '..payout-tracker-sub.children...payout-tracker-body.children...{"name":["ALL"],"type":"payout-ajo-btn"}.className..',
            "outputs": [
                {"id": "payout-tracker-sub", "property": "children"},
                {"id": "payout-tracker-body", "property": "children"},
                [
                    {"id": {"type": "payout-ajo-btn", "name": name}, "property": "className"}
                    for name in names
                ],
            ],
            "inputs": [
                {"id": "payout-ajo", "property": "data", "value": ajo_name},
                {"id": "payout-selected", "property": "data", "value": "kemi_a"},
            ],
            "changedPropIds": ["payout-ajo.data"],
            "state": [],
        },
    )
    return response


def test_callback_shows_only_the_requested_created_ajo():
    response = _post_tracker("admin", "admintest", "Sister Circle Ajo")
    body = json.dumps(response.get_json()["response"]["payout-tracker-body"])

    assert response.status_code == 200
    assert "AJO-SCA-01-0312" in body
    assert "AJO-BBM" not in body
    classes = response.get_json()["response"]
    assert classes['{"name":"Sister Circle Ajo","type":"payout-ajo-btn"}']["className"] == "on"
    assert classes['{"name":"Brum Builders","type":"payout-ajo-btn"}']["className"] == ""


def test_callback_rejects_an_ajo_the_creator_does_not_own():
    response = _post_tracker("admin", "admintest", "Other Hands Ajo")
    body = json.dumps(response.get_json()["response"]["payout-tracker-body"])

    assert response.status_code == 200
    assert "AJO-BBM-01-0228" in body
    assert "Other Hands" not in body
    assert "AJO-SCA" not in body


def test_callback_member_and_non_creator_receive_no_tracker_rows():
    for role, username in (("member", "membertest"), ("admin", "not-the-creator")):
        response = _post_tracker(role, username, "Sister Circle Ajo")
        payload = response.get_json()["response"]
        body = json.dumps(payload["payout-tracker-body"])

        assert response.status_code == 200
        assert payload["payout-tracker-sub"]["children"] == ""
        assert "AJO-" not in body
        assert "Hold to release" not in body
        assert payload['{"name":"Sister Circle Ajo","type":"payout-ajo-btn"}']["className"] == ""


def test_layout_lists_only_created_ajos(monkeypatch):
    monkeypatch.setattr("pages.payouts.visible_ajo_names", lambda username, role, document=None: ["Brum Builders"])
    monkeypatch.setattr(
        "pages.payouts.resolve_ajo",
        lambda requested, username, role, document=None: "Brum Builders",
    )

    text = str(payouts_layout("admin", "admintest"))

    assert "Payouts Tracker" in text
    assert "Brum Builders" in text
    assert "Sister Circle Ajo" not in text
    assert "role-btn" not in text
