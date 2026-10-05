"""Members page: Ajo picker, shared tabs, and the admin management panel."""

from flask import session

from app_dash_web import app, render_page, render_shell
from pages.members import (
    ADMIN_PERSONA_ID,
    MEMBER_PERSONA_ID,
    compose_view,
    groups_for_persona,
    invite_message,
    layout,
    member_rows,
    members_csv,
    persona_for_session,
    resolve_ajo,
)
from pages.personas import BRUM_BUILDERS, SISTER_CIRCLE


def _text(node):
    chunks = []

    def walk(item):
        if item is None or isinstance(item, (bool, int, float)):
            return
        if isinstance(item, str):
            chunks.append(item)
            return
        if isinstance(item, (list, tuple)):
            for child in item:
                walk(child)
            return
        children = getattr(item, "children", None)
        if children is not None:
            walk(children)
        options = getattr(item, "options", None)
        if options:
            for option in options:
                if isinstance(option, dict):
                    walk(option.get("label"))

    walk(node)
    return "\n".join(chunks)


def _hidden(node):
    style = getattr(node, "style", None) or {}
    return style.get("display") == "none"


def test_callbacks_are_registered():
    joined = " ".join(app.callback_map)
    assert "members-panel" in joined
    assert "members-download" in joined
    assert "members-notice" in joined


def test_admin_and_member_personas_follow_the_server_role():
    assert persona_for_session("admin", "admintest") == ADMIN_PERSONA_ID
    assert persona_for_session("member", "membertest") == MEMBER_PERSONA_ID
    assert persona_for_session("member", "admintest") == MEMBER_PERSONA_ID
    assert groups_for_persona(ADMIN_PERSONA_ID) == [BRUM_BUILDERS, SISTER_CIRCLE]
    assert groups_for_persona(MEMBER_PERSONA_ID) == [BRUM_BUILDERS, SISTER_CIRCLE]
    assert groups_for_persona("persona-06") == [BRUM_BUILDERS]
    assert groups_for_persona("persona-08") == [SISTER_CIRCLE]


def test_ajo_choice_stays_inside_the_persona_groups():
    assert resolve_ajo("persona-06", SISTER_CIRCLE) == BRUM_BUILDERS
    assert resolve_ajo("persona-08", SISTER_CIRCLE) == SISTER_CIRCLE
    assert resolve_ajo("persona-08", "Not an Ajo") == SISTER_CIRCLE


def test_member_list_drops_the_uk_score_and_renames_circles():
    for role, username in (("admin", "admintest"), ("member", "membertest")):
        text = _text(layout(role, username))
        assert "UK score" not in text
        assert "Origin" not in text
        assert "Circles" not in text
        assert "Sort: Credit score" not in text
        assert "Ajos" in text
        assert "Members" in text
        assert "Activity" in text
        assert "Communication" in text
        assert BRUM_BUILDERS in text
        assert SISTER_CIRCLE in text
        assert "credit-verified" in text
        assert "usernames only" in text


def test_lists_are_names_and_status_for_the_selected_ajo():
    brum = _text(compose_view("member", "membertest", BRUM_BUILDERS, "members", "all", "pos")["panel"])
    sister = _text(compose_view("member", "membertest", SISTER_CIRCLE, "members", "all", "pos")["panel"])
    assert "Tunde Exampleonly" in brum
    assert "Kelechi Mockmember" not in brum
    assert "Kelechi Mockmember" in sister
    assert "Tunde Exampleonly" not in sister
    assert "Amina Testperson" in brum
    assert "Paid" in brum or "Received" in brum
    for blob in (brum, sister):
        assert "@example.test" not in blob
        assert "demo1" not in blob
        assert "UK score" not in blob


def test_admin_panel_is_visible_only_for_the_admin_role():
    admin = layout("admin", "admintest")
    admin_text = _text(admin)
    for label in (
        "Quick actions",
        "Manage positions",
        "Export member list",
        "Refresh data",
        "Invite member",
        "Member statistics",
        "Created by",
        "Amina Testperson",
        "Contribution amount",
        "Available spots",
    ):
        assert label in admin_text

    member = layout("member", "membertest")
    member_text = _text(member)
    for label in ("Quick actions", "Manage positions", "Invite member", "Member statistics", "Created by"):
        assert label not in member_text
    summary = _find(member, "members-summary")
    assert summary is not None
    assert _hidden(summary)


def test_tabs_swap_the_panel_and_keep_names_and_status():
    activity = compose_view("admin", "admintest", BRUM_BUILDERS, "activity", "all", "pos")
    communication = compose_view("member", "membertest", SISTER_CIRCLE, "communication", "all", "name")
    activity_text = _text(activity["panel"])
    communication_text = _text(communication["panel"])
    assert activity["tab_classes"] == ["", "on", ""]
    assert "Activity" in activity_text
    assert "Chidi Sampledata" in activity_text
    assert communication["tab_classes"] == ["", "", "on"]
    assert "Communication" in communication_text
    assert "does not send email or SMS" in communication_text
    assert communication["tools_style"].get("display") == "none"
    assert activity["summary_style"] == {}
    assert communication["summary_style"].get("display") == "none"


def test_status_filter_and_name_sort():
    filtered = compose_view("member", "membertest", BRUM_BUILDERS, "members", "pending", "name")
    rows = member_rows(BRUM_BUILDERS, MEMBER_PERSONA_ID)
    pending = [row for row in rows if row["status"] == "pending"]
    text = _text(filtered["panel"])
    assert pending
    assert pending[0]["name"] in text
    assert "Tunde Exampleonly" not in text or pending[0]["name"] == "Tunde Exampleonly"
    paid_names = [row["name"] for row in rows if row["status"] == "paid"]
    assert paid_names
    assert paid_names[0] not in text
    assert filtered["filter_classes"][FILTER_INDEX["pending"]] == "on"


def test_csv_is_names_and_status_only():
    csv_text = members_csv(BRUM_BUILDERS, ADMIN_PERSONA_ID)
    assert csv_text.startswith("username,name,status\n")
    assert "amina.testperson,Amina Testperson," in csv_text
    assert "@example.test" not in csv_text
    assert "demo1" not in csv_text
    assert "password" not in csv_text
    assert "score" not in csv_text


def test_invite_collects_a_username_only():
    assert "Email addresses are not collected" in invite_message("a@b.test", BRUM_BUILDERS)
    assert "Enter a username" in invite_message("  ", SISTER_CIRCLE)
    queued = invite_message("newmember", BRUM_BUILDERS)
    assert "Invite queued for @newmember" in queued
    assert "Nothing is sent" in queued
    assert "@example.test" not in queued


def test_shell_uses_the_session_role_for_members():
    with app.server.test_request_context():
        session.clear()
        session["role"] = "admin"
        session["username"] = "admintest"
        shell = render_shell("members", "member")
        text = _text(shell)
        assert "Manage positions" in text
        assert "PayoutsTracker" in text
    with app.server.test_request_context():
        session.clear()
        session["role"] = "member"
        session["username"] = "membertest"
        shell = render_shell("members", "admin")
        text = _text(shell)
        assert "Manage positions" not in text
        assert "Activity" in text
        assert "PayoutsTracker" not in text


def test_render_page_covers_members_for_both_roles():
    for role in ("member", "admin"):
        page = render_page("members", role, "admintest" if role == "admin" else "membertest")
        assert page is not None
        assert "Members" in _text(page)


FILTER_INDEX = {"all": 0, "paid": 1, "pending": 2, "received": 3}


def _find(node, component_id):
    found = []

    def walk(item):
        if item is None or isinstance(item, (str, bool, int, float)):
            return
        if isinstance(item, (list, tuple)):
            for child in item:
                walk(child)
            return
        if getattr(item, "id", None) == component_id:
            found.append(item)
        walk(getattr(item, "children", None))

    walk(node)
    return found[0] if found else None
