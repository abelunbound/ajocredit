"""Dummy circles record their creator, who is the admin of that Ajo."""

import json
from pathlib import Path

import pytest
from flask import session

from app_dash_web import app, render_shell
from pages.circle import layout as circle_layout
from pages.circles import circle_records, load_dummy_circles
from pages.personas import EXAMPLE_PERSONAS_PATH

REPO_ROOT = Path(__file__).resolve().parent


def _example_document():
    return json.loads(EXAMPLE_PERSONAS_PATH.read_text(encoding="utf-8"))


def test_each_dummy_circle_records_its_creator_as_admin():
    records = circle_records(_example_document())

    assert [circle["name"] for circle in records] == ["Brum Builders", "Sister Circle Ajo"]
    for circle in records:
        assert circle["created_by"] == "persona-01"
        assert circle["creator_name"] == "Amina Testperson"
        assert circle["admin_id"] == circle["created_by"]
        assert circle["admin_name"] == circle["creator_name"]
        admins = [member for member in circle["members"] if member["role_in_ajo"] == "admin"]
        assert [member["id"] for member in admins] == [circle["created_by"]]
        assert all(
            member["role_in_ajo"] == "member"
            for member in circle["members"]
            if member["id"] != circle["created_by"]
        )
        assert "password" not in circle
        assert "email" not in json.dumps(circle)


def test_circle_records_reject_a_creator_who_is_not_the_admin():
    document = _example_document()
    document["personas"][0]["role"] = "member"
    document["personas"][1]["role"] = "admin"

    with pytest.raises(ValueError, match="creator"):
        circle_records(document)


def test_load_dummy_circles_prefers_the_local_personas_file(tmp_path, monkeypatch):
    document = _example_document()
    document["personas"][0]["name"] = "Amina Localonly"
    local_file = tmp_path / "personas.json"
    local_file.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr("pages.circles.DEFAULT_PERSONAS_PATH", local_file)

    records = load_dummy_circles()

    assert records[0]["creator_name"] == "Amina Localonly"
    assert records[0]["admin_name"] == "Amina Localonly"
    assert records[1]["admin_id"] == records[1]["created_by"]


def test_load_dummy_circles_falls_back_to_the_example(tmp_path, monkeypatch):
    missing = tmp_path / "personas.json"
    monkeypatch.setattr("pages.circles.DEFAULT_PERSONAS_PATH", missing)

    records = load_dummy_circles()

    assert {circle["name"] for circle in records} == {"Brum Builders", "Sister Circle Ajo"}
    assert {circle["created_by"] for circle in records} == {"persona-01"}


def test_my_ajo_shows_the_viewers_groups_for_both_stub_roles():
    """The client-supplied role does not change which Ajo is on screen."""
    with app.server.test_request_context():
        session.clear()
        session["role"] = "admin"
        session["username"] = "admintest"
        admin_text = str(render_shell("circle", "member"))
        assert "Rotation timeline" in admin_text
        assert "Amina Testperson" in admin_text
        assert "Brum Builders" in admin_text
        assert "Sister Circle Ajo" in admin_text
        assert "role-btn" not in admin_text
        assert "demo1" not in admin_text
        assert "@example.test" not in admin_text
        assert "PayoutsTracker" in admin_text

        session.clear()
        session["role"] = "member"
        session["username"] = "membertest"
        member_text = str(render_shell("circle", "admin"))
        assert "Rotation timeline" in member_text
        assert "Tunde Exampleonly" in member_text
        assert "Sister Circle Ajo" not in member_text
        assert "PayoutsTracker" not in member_text
        assert "role-btn" not in member_text
        assert "demo1" not in member_text
        assert "@example.test" not in member_text


def test_circle_layout_reads_the_loader(monkeypatch):
    monkeypatch.setattr(
        "pages.my_ajo.load_ajo_document",
        lambda: {
            "groups": [
                {"name": "Brum Builders", "created_by": "persona-01"},
                {"name": "Sister Circle Ajo", "created_by": "persona-01"},
            ],
            "personas": [
                {
                    "id": "persona-01",
                    "name": "Fixture Creator",
                    "role": "admin",
                    "groups": ["Brum Builders", "Sister Circle Ajo"],
                },
                {
                    "id": "persona-06",
                    "name": "Member Fixture",
                    "role": "member",
                    "groups": ["Brum Builders"],
                },
            ],
        },
    )

    text = str(circle_layout("member"))
    assert "Fixture Creator" in text
    assert "Member Fixture" in text
    assert "Rotation timeline" in text
    assert "Amina Testperson" not in text
