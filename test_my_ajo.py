"""My Ajo is the original rotation screen, with group tabs when needed."""

import json
from pathlib import Path

import pytest
from flask import session

from app_dash_web import app, render_page, render_shell
from pages.my_ajo import ajos_for_viewer, layout, load_ajo_document, resolve_viewer
from pages.personas import EXAMPLE_PERSONAS_PATH

REPO_ROOT = Path(__file__).resolve().parent


def _example_document():
    return json.loads(EXAMPLE_PERSONAS_PATH.read_text(encoding="utf-8"))


def _names(cards):
    return [card["name"] for card in cards]


def test_admin_sees_both_ajos_and_the_recorded_creator():
    document = _example_document()
    viewer = resolve_viewer(document, "admintest", "member")
    cards = ajos_for_viewer(document, viewer)

    assert viewer["id"] == "persona-01"
    assert viewer["name"] == "Amina Testperson"
    assert _names(cards) == ["Brum Builders", "Sister Circle Ajo"]
    for card in cards:
        assert card["viewer_is_admin"] is True
        assert card["created_by"] == "persona-01"
        assert card["creator_name"] == "Amina Testperson"
        assert card["member_count"] == len(card["members"])
        assert card["pot"] == card["amount"] * card["member_count"]
        assert "password" not in card
        assert "email" not in json.dumps(card)


def test_member_sees_only_their_ajo():
    document = _example_document()
    viewer = resolve_viewer(document, "membertest", "admin")
    cards = ajos_for_viewer(document, viewer)

    assert viewer["id"] == "persona-06"
    assert viewer["name"] == "Tunde Exampleonly"
    assert _names(cards) == ["Brum Builders"]
    assert cards[0]["viewer_is_admin"] is False
    assert cards[0]["creator_name"] == "Amina Testperson"
    assert any(member["is_viewer"] and member["name"] == "Tunde Exampleonly" for member in cards[0]["members"])


def test_missing_creator_still_renders_and_uses_the_persona_role():
    document = _example_document()
    for group in document["groups"]:
        group.pop("created_by", None)
    viewer = resolve_viewer(document, "admintest", "admin")
    cards = ajos_for_viewer(document, viewer)

    assert _names(cards) == ["Brum Builders", "Sister Circle Ajo"]
    for card in cards:
        assert card["created_by"] is None
        assert card["creator_name"] is None
        assert card["viewer_is_admin"] is True

    member = resolve_viewer(document, "membertest", "member")
    member_cards = ajos_for_viewer(document, member)
    assert member_cards[0]["viewer_is_admin"] is False
    assert member_cards[0]["creator_name"] is None


def test_load_ajo_document_prefers_the_local_file(tmp_path, monkeypatch):
    document = _example_document()
    document["personas"][0]["name"] = "Amina Localonly"
    local_file = tmp_path / "personas.json"
    local_file.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr("pages.my_ajo.DEFAULT_PERSONAS_PATH", local_file)

    loaded = load_ajo_document()
    viewer = resolve_viewer(loaded, "admintest", "admin")

    assert viewer["name"] == "Amina Localonly"


def test_load_ajo_document_falls_back_to_the_example(tmp_path, monkeypatch):
    monkeypatch.setattr("pages.my_ajo.DEFAULT_PERSONAS_PATH", tmp_path / "missing.json")

    loaded = load_ajo_document()
    viewer = resolve_viewer(loaded, "admintest", "admin")

    assert viewer["name"] == "Amina Testperson"


def test_layout_restores_the_rotation_screen_and_hides_secrets():
    text = str(layout("admin", "admintest", _example_document()))

    assert "Rotation timeline" in text
    assert "Circle rules" in text
    assert "Contribution progress" in text
    assert "Brum Builders" in text
    assert "Sister Circle Ajo" in text
    assert "my-ajo-btn" in text
    assert "Amina Testperson" in text
    assert text.count("children='you'") == 1
    assert "Verified" in text
    assert "Month 3/8" in text
    assert "Birmingham, UK · £500 x 8 monthly · pot £4,000" in text
    assert "£500 monthly · autopay 1st" in text
    assert "Fixed by join-date" in text
    assert "48 hours" in text
    assert "Only after payout month" in text
    assert "680" in text
    assert "7 of 8 collected" in text
    assert "£3,500 / £4,000" in text
    assert "Delay Cover covering £500 for @seyi_d" in text
    assert "Auto-loan" not in text
    assert "Kelechi Mockmember" not in text
    assert "Ifeoma Sandbox" not in text
    assert "You are the admin of this Ajo." not in text
    assert "demo1" not in text
    assert "@example.test" not in text
    assert "role-btn" not in text


def test_member_layout_lists_one_ajo():
    text = str(layout("member", "membertest", _example_document()))

    assert "Tunde Exampleonly" in text
    assert text.count("children='you'") == 1
    assert "Rotation timeline" in text
    assert "Month 3/8" in text
    assert "Brum Builders" in text
    assert "Sister Circle Ajo" not in text
    assert "Kelechi Mockmember" not in text
    assert "You are a member of this Ajo." not in text
    assert "You are the admin of this Ajo." not in text
    assert "Delay Cover" in text
    assert "Auto-loan" not in text


def test_shell_follows_the_server_session_not_the_client_role():
    with app.server.test_request_context():
        session.clear()
        session["username"] = "admintest"
        session["role"] = "admin"
        admin_text = str(render_shell("circle", "member"))
        assert "My Ajo" in admin_text
        assert "PayoutsTracker" in admin_text
        assert "Rotation timeline" in admin_text
        assert "Amina Testperson" in admin_text
        assert "Sister Circle Ajo" in admin_text
        assert "Kelechi Mockmember" not in admin_text
        assert "role-btn" not in admin_text

        session.clear()
        session["username"] = "membertest"
        session["role"] = "member"
        member_text = str(render_shell("circle", "admin"))
        assert "My Ajo" in member_text
        assert "PayoutsTracker" not in member_text
        assert "Tunde Exampleonly" in member_text
        assert "Sister Circle Ajo" not in member_text
        assert "role-btn" not in member_text


def test_render_page_accepts_the_existing_role_argument():
    with app.server.test_request_context():
        session.clear()
        page = render_page("circle", "admin")
        text = str(page)
        assert "Rotation timeline" in text
        assert "Amina Testperson" in text


def test_nav_label_is_my_ajo():
    from pages.data import CRUMBS, NAV

    labels = [label for _key, label, _icon in NAV]
    assert "My Ajo" in labels
    assert "MyAjo" not in labels
    assert CRUMBS["circle"] == ["AjoFinance", "My Ajo"]


def _post_ajo(role, username, ajo_name, names):
    client = app.server.test_client()
    with client.session_transaction() as sess:
        sess["role"] = role
        sess["username"] = username
    response = client.post(
        "/_dash-update-component",
        json={
            "output": '..my-ajo-body.children...{"name":["ALL"],"type":"my-ajo-btn"}.className..',
            "outputs": [
                {"id": "my-ajo-body", "property": "children"},
                [
                    {"id": {"type": "my-ajo-btn", "name": name}, "property": "className"}
                    for name in names
                ],
            ],
            "inputs": [{"id": "my-ajo-selected", "property": "data", "value": ajo_name}],
            "changedPropIds": ["my-ajo-selected.data"],
            "state": [],
        },
    )
    return response


def test_callback_switches_the_whole_screen_to_the_other_ajo():
    response = _post_ajo("admin", "admintest", "Sister Circle Ajo", ["Brum Builders", "Sister Circle Ajo"])
    payload = response.get_json()["response"]
    body = json.dumps(payload["my-ajo-body"], ensure_ascii=False)

    assert response.status_code == 200
    assert "Sister Circle Ajo" in body
    assert "Ifeoma Sandbox" in body
    assert "Kelechi Mockmember" in body
    assert "Amina Testperson" in body
    assert "Tunde Exampleonly" not in body
    assert "Yewande Faketest" not in body
    assert "Month 3/7" in body
    assert "£250 x 7 monthly" in body
    assert "pot £1,750" in body
    assert "6 of 7 collected" in body
    assert "Delay Cover covering £250 for @ifeoma_s" in body
    assert "Auto-loan" not in body
    assert "@example.test" not in body
    assert payload['{"name":"Sister Circle Ajo","type":"my-ajo-btn"}']["className"] == "on"
    assert payload['{"name":"Brum Builders","type":"my-ajo-btn"}']["className"] == ""


def test_callback_rejects_an_ajo_the_viewer_does_not_belong_to():
    response = _post_ajo("member", "membertest", "Sister Circle Ajo", ["Brum Builders"])
    payload = response.get_json()["response"]
    body = json.dumps(payload["my-ajo-body"], ensure_ascii=False)

    assert response.status_code == 200
    assert "Brum Builders" in body
    assert "Tunde Exampleonly" in body
    assert "Sister Circle Ajo" not in body
    assert "Ifeoma Sandbox" not in body
    assert "Kelechi Mockmember" not in body
    assert payload['{"name":"Brum Builders","type":"my-ajo-btn"}']["className"] == "on"


def test_unreadable_persona_file_does_not_crash_the_page(monkeypatch):
    def _boom():
        raise ValueError("bad personas")

    monkeypatch.setattr("pages.my_ajo.load_ajo_document", _boom)
    text = str(layout("member", "membertest"))
    assert "My Ajo is unavailable" in text
    assert "My Ajo" in text
