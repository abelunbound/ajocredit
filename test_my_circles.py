"""Sidebar My circles reads persona groups and the circle-actions fixture.

Circle names are not hardcoded in the sidebar. Payouts Tracker stays behind
the creator gate: admintest sees it, and membertest does not.
"""

import json
from pathlib import Path

import pytest
from flask import session

from app_dash_web import app, render_shell, sidebar
from pages.my_circles import (
    DEFAULT_ACTIONS_PATH,
    load_circle_actions,
    load_circle_names,
    my_circles_rows,
)
from pages.personas import EXAMPLE_PERSONAS_PATH

REPO_ROOT = Path(__file__).resolve().parent


def _text(role, username="signed-in", page="home"):
    with app.server.test_request_context():
        session["role"] = role
        session["username"] = username
        return str(render_shell(page, "admin" if role == "member" else "member"))


def test_sidebar_lists_persona_groups_and_actions_in_order():
    names = load_circle_names(EXAMPLE_PERSONAS_PATH)
    actions = load_circle_actions()

    assert names == ["Brum Builders", "Sister Circle Ajo"]
    assert [action["id"] for action in actions] == ["create-circle", "join-ajo"]
    assert [action["label"] for action in actions] == ["Create circle", "Join Ajo"]
    assert all(action["icon"] == "plus" for action in actions)

    text = str(sidebar("home", "admin", "admintest"))
    assert "Brum Builders" in text
    assert "Sister Circle Ajo" in text
    assert text.index("Brum Builders") < text.index("Sister Circle Ajo")
    assert text.index("Sister Circle Ajo") < text.index("Create circle")
    assert text.index("Create circle") < text.index("Join Ajo")
    assert "My circles" in text


def test_circle_names_follow_persona_document_order(tmp_path):
    document = json.loads(EXAMPLE_PERSONAS_PATH.read_text(encoding="utf-8"))
    document["groups"] = list(reversed(document["groups"]))
    path = tmp_path / "personas.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    assert load_circle_names(path) == ["Sister Circle Ajo", "Brum Builders"]


def test_missing_local_personas_file_uses_example(tmp_path, monkeypatch):
    monkeypatch.setattr("pages.personas.DEFAULT_PERSONAS_PATH", tmp_path / "personas.json")

    assert load_circle_names() == ["Brum Builders", "Sister Circle Ajo"]


def test_local_personas_file_wins_over_example(tmp_path, monkeypatch):
    document = json.loads(EXAMPLE_PERSONAS_PATH.read_text(encoding="utf-8"))
    document["groups"] = list(reversed(document["groups"]))
    local_file = tmp_path / "personas.json"
    local_file.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr("pages.personas.DEFAULT_PERSONAS_PATH", local_file)

    assert load_circle_names() == ["Sister Circle Ajo", "Brum Builders"]


def test_sidebar_rows_come_from_loaders(monkeypatch):
    monkeypatch.setattr("pages.my_circles.load_circle_names", lambda path=None: ["North Circle"])
    monkeypatch.setattr(
        "pages.my_circles.load_circle_actions",
        lambda path=None: [
            {"id": "create-circle", "label": "Start a circle", "icon": "plus"},
            {"id": "join-ajo", "label": "Find an Ajo", "icon": "plus"},
        ],
    )

    text = str(my_circles_rows())
    assert "North Circle" in text
    assert "Brum Builders" not in text
    assert "Sister Circle" not in text
    assert "Start a circle" in text
    assert "Find an Ajo" in text
    assert "Create circle" not in text
    assert text.index("Start a circle") < text.index("Find an Ajo")


def test_actions_file_rejects_join_before_create(tmp_path):
    path = tmp_path / "circle_actions.json"
    path.write_text(
        json.dumps(
            {
                "actions": [
                    {"id": "join-ajo", "label": "Join Ajo", "icon": "plus"},
                    {"id": "create-circle", "label": "Create circle", "icon": "plus"},
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Join Ajo"):
        load_circle_actions(path)


def test_actions_file_is_tracked():
    assert DEFAULT_ACTIONS_PATH == REPO_ROOT / "data" / "circle_actions.json"
    assert DEFAULT_ACTIONS_PATH.is_file()


def test_member_sidebar_hides_payouts_and_still_lists_circles():
    text = _text("member", "membertest")

    assert "PayoutsTracker" not in text
    assert "Brum Builders" in text
    assert "Sister Circle Ajo" not in text
    assert "Create circle" in text
    assert "Join Ajo" in text
    assert "role-btn" not in text
    assert "@membertest" in text


def test_admin_sidebar_keeps_payouts_tracker():
    text = _text("admin", "admintest")

    assert "PayoutsTracker" in text
    assert "Brum Builders" in text
    assert "Sister Circle Ajo" in text
    assert text.index("Brum Builders") < text.index("Sister Circle Ajo")
    assert "Join Ajo" in text
    assert text.index("Create circle") < text.index("Join Ajo")
    assert "role-btn" not in text
