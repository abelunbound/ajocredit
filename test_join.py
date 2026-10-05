"""Join Ajo search, card actions, and invitation dialog."""

from flask import session

from app_dash_web import app as dash_app
from app_dash_web import next_state, render_shell
from pages.ajo_catalog import GROUPS, card_actions, filter_groups, group_by_id
from pages.join import apply_join, dispatch_join_action, invite_problem, layout, summary_text
from stub_auth import gate_page


def _walk(node):
    if node is None or isinstance(node, (str, int, float, bool)):
        return
    if isinstance(node, (list, tuple)):
        for item in node:
            yield from _walk(item)
        return
    yield node
    children = getattr(node, "children", None)
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _walk(child)
    elif children is not None:
        yield from _walk(children)


def _find(node, node_id):
    for item in _walk(node):
        if getattr(item, "id", None) == node_id:
            return item
    raise AssertionError(f"missing {node_id}")


def _action_labels(card):
    row = next(item for item in _walk(card) if getattr(item, "className", None) == "join-actions")
    labels = []
    for child in row.children:
        assert child.__class__.__name__ == "Button"
        assert isinstance(child.children, str)
        labels.append(child.children)
    return labels


class TestCatalogFilters:
    def test_search_matches_name_or_city(self):
        names = [group["name"] for group in filter_groups("member", search="sister circle")]
        assert names == ["Sister Circle Ajo"]
        assert [group["name"] for group in filter_groups("member", search="sisters")] == ["Wolverhampton Sisters"]
        cities = {group["city"] for group in filter_groups("admin", search="birmingham")}
        assert "Birmingham" in cities
        assert "Leeds" not in cities

    def test_status_filters(self):
        active = {group["id"] for group in filter_groups("member", status="active")}
        assert "brum-builders" in active
        assert "manchester-market" not in active
        completed = {group["id"] for group in filter_groups("member", status="completed")}
        assert completed == {"manchester-market", "wolverhampton-sisters"}
        opened = {group["id"] for group in filter_groups("member", status="open")}
        assert "coventry-savers" in opened
        assert "brum-builders" not in opened

    def test_date_range_keeps_overlapping_circles(self):
        in_2026 = {group["id"] for group in filter_groups("member", date_from="2026-01-01", date_to="2026-12-31")}
        assert "brum-builders" in in_2026
        assert "manchester-market" not in in_2026
        in_2024 = {group["id"] for group in filter_groups("member", date_from="2024-03-01", date_to="2024-06-01")}
        assert "manchester-market" in in_2024
        assert "coventry-savers" not in in_2024

    def test_reversed_range_is_swapped(self):
        forward = filter_groups("admin", date_from="2026-01-01", date_to="2026-02-01")
        backward = filter_groups("admin", date_from="2026-02-01", date_to="2026-01-01")
        assert [group["id"] for group in forward] == [group["id"] for group in backward]

    def test_groups_i_manage_follow_the_creator(self):
        admin_ids = [group["id"] for group in filter_groups("admin", status="managed")]
        assert admin_ids == ["brum-builders", "sister-circle", "wolverhampton-sisters"]
        assert filter_groups("member", status="managed") == []

    def test_creator_actions_include_manage_members_on_one_list(self):
        brum = group_by_id("brum-builders")
        assert card_actions(brum, "admin") == ["view", "invite", "manage"]
        assert card_actions(brum, "member") == ["view", "invite"]
        eastside = group_by_id("eastside-friends")
        assert "manage" not in card_actions(eastside, "admin")
        coventry = group_by_id("coventry-savers")
        assert card_actions(coventry, "member") == ["view", "invite", "join"]


class TestJoinRequests:
    def test_member_can_join_an_open_circle_once(self):
        joined, notice = apply_join("coventry-savers", "member", [])
        assert joined == ["coventry-savers"]
        assert notice == "Join request sent for Coventry Savers."
        again, again_notice = apply_join("coventry-savers", "member", joined)
        assert again == joined
        assert "already in" in again_notice

    def test_full_or_closed_circles_refuse_join(self):
        joined, notice = apply_join("brum-builders", "member", [])
        assert joined == []
        assert "already in" in notice
        joined, notice = apply_join("manchester-market", "member", [])
        assert joined == []
        assert "not open" in notice

    def test_invite_validation(self):
        assert invite_problem("", "") == "Enter an email address."
        assert invite_problem("not-an-email", "") == "Enter a valid email address."
        assert invite_problem("ada@example.test", "x" * 501).startswith("Keep")
        assert invite_problem("ada@example.test", "See you there") is None

    def test_dispatch_opens_invite_and_queues_it(self):
        opened = dispatch_join_action(
            {"type": "ajo-invite", "gid": "coventry-savers"},
            role="member",
            joined_ids=[],
            view_gid=None,
            invite_gid=None,
            manage_gid=None,
            email="",
            message="",
            rev=0,
        )
        assert opened["invite_gid"] == "coventry-savers"
        refused = dispatch_join_action(
            "join-invite-send",
            role="member",
            joined_ids=[],
            view_gid=None,
            invite_gid="coventry-savers",
            manage_gid=None,
            email="ada",
            message="",
            rev=0,
        )
        assert refused["invite_gid"] == "coventry-savers"
        assert refused["invite_error"] == "Enter a valid email address."
        sent = dispatch_join_action(
            "join-invite-send",
            role="member",
            joined_ids=[],
            view_gid=None,
            invite_gid="coventry-savers",
            manage_gid=None,
            email="ada@example.test",
            message="Hello",
            rev=2,
        )
        assert sent["invite_gid"] is None
        assert sent["clear_form"] is True
        assert sent["notice"] == "Invitation queued for ada@example.test."

    def test_dispatch_hides_manage_from_non_creators(self):
        blocked = dispatch_join_action(
            {"type": "ajo-manage", "gid": "brum-builders"},
            role="member",
            joined_ids=[],
            view_gid=None,
            invite_gid=None,
            manage_gid=None,
            email="",
            message="",
            rev=0,
        )
        assert blocked["manage_gid"] is None
        assert "creator" in blocked["notice"]
        allowed = dispatch_join_action(
            {"type": "ajo-manage", "gid": "brum-builders"},
            role="admin",
            joined_ids=[],
            view_gid=None,
            invite_gid=None,
            manage_gid=None,
            email="",
            message="",
            rev=0,
        )
        assert allowed["manage_gid"] == "brum-builders"
        not_theirs = dispatch_join_action(
            {"type": "ajo-manage", "gid": "coventry-savers"},
            role="admin",
            joined_ids=[],
            view_gid=None,
            invite_gid=None,
            manage_gid=None,
            email="",
            message="",
            rev=0,
        )
        assert not_theirs["manage_gid"] is None

    def test_dispatch_view_and_join(self):
        viewed = dispatch_join_action(
            {"type": "ajo-view", "gid": "leeds-family-pot"},
            role="admin",
            joined_ids=[],
            view_gid=None,
            invite_gid="coventry-savers",
            manage_gid=None,
            email="",
            message="",
            rev=1,
        )
        assert viewed["view_gid"] == "leeds-family-pot"
        assert viewed["invite_gid"] is None
        joined = dispatch_join_action(
            {"type": "ajo-join", "gid": "leeds-family-pot"},
            role="admin",
            joined_ids=[],
            view_gid=None,
            invite_gid=None,
            manage_gid=None,
            email="",
            message="",
            rev=1,
        )
        assert joined["joined_ids"] == ["leeds-family-pot"]
        assert joined["rev"] == 2


class TestJoinScreen:
    def test_cards_put_actions_on_one_row(self):
        admin = layout("admin")
        member = layout("member")
        for role_name, screen in (("admin", admin), ("member", member)):
            for group in GROUPS:
                card = _find(screen, f"ajo-card-{group['id']}")
                labels = _action_labels(card)
                expected = [label for key, label in (
                    ("view", "View details"),
                    ("invite", "Invite Member"),
                    ("manage", "Manage Members"),
                    ("join", "Join"),
                ) if key in card_actions(group, role_name)]
                assert labels == expected

    def test_member_cards_have_no_manage_button(self):
        screen = layout("member")
        labels = []
        for group in GROUPS:
            labels.extend(_action_labels(_find(screen, f"ajo-card-{group['id']}")))
        assert "Manage Members" not in labels
        assert labels.count("View details") == len(GROUPS)
        assert "Invite Member" in labels
        assert "Join" in labels

    def test_admin_manage_button_only_on_circles_they_created(self):
        screen = layout("admin")
        managed = []
        for group in GROUPS:
            labels = _action_labels(_find(screen, f"ajo-card-{group['id']}"))
            if "Manage Members" in labels:
                managed.append(group["id"])
        assert managed == ["brum-builders", "sister-circle", "wolverhampton-sisters"]

    def test_search_filter_and_date_range_are_on_the_page(self):
        screen = layout("member")
        text = str(screen)
        assert "Join Ajo" in text
        assert "Search circles" in text
        assert "All groups" in text
        assert "Open to join" in text
        assert "Groups I manage" in text
        assert "Date range" in text
        assert "join-date-from" in text
        assert "join-date-to" in text
        assert "Invite Member to Group" in text
        assert "Email Address" in text
        assert "Personal Message (Optional)" in text
        assert "Send Invitation" in text
        assert "This message will be included with the invitation link." in text

    def test_summary_keeps_circles_plural(self):
        assert summary_text(1, 8) == "Showing 1 of 8 circles"
        assert summary_text(8, 8) == "Showing 8 of 8 circles"

    def test_gate_and_sidebar(self):
        assert gate_page("join", None) == "signin"
        assert gate_page("join", "member") == "join"
        assert gate_page("join", "admin") == "join"
        with dash_app.server.test_request_context():
            session.clear()
            page, _rev, error = next_state({"type": "nav-btn", "page": "join"}, "home", 0, "", "")
            assert page == "signin"
            assert error == ""
            session["username"] = "membertest"
            session["role"] = "member"
            page, _rev, error = next_state({"type": "nav-btn", "page": "join"}, "home", 1, "", "")
            assert page == "join"
            shell = str(render_shell("join", None))
            assert shell.index("Create circle") < shell.index("Join Ajo")
            assert "PayoutsTracker" not in shell
            assert "Date range" in shell
            assert "Join Ajo" in shell
            session["username"] = "admintest"
            session["role"] = "admin"
            admin_shell = str(render_shell("home", None))
            assert "Join Ajo" in admin_shell
            assert "PayoutsTracker" in admin_shell

    def test_join_callbacks_are_registered(self):
        keys = [str(key) for key in dash_app.callback_map]
        assert any("join-results" in key for key in keys)
        assert any("join-invite-modal" in key for key in keys)
