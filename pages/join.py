"""Join Ajo search screen.

The first step is a searchable list of circles. Each card keeps
View details, Invite Member, and Manage Members on one row. Manage Members
is rendered only for the creator of that circle. Join is added on the same
row when the circle is open and the viewer is not already a member.
"""

from __future__ import annotations

import re

from dash import ALL, Input, Output, State, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate
from flask import session

from pages.ajo_catalog import (
    ACTION_LABELS,
    GROUPS,
    GROUP_BY_ID,
    can_join,
    card_actions,
    displayed_member_count,
    filter_groups,
    group_by_id,
    role_label,
    viewer_is_creator,
    viewer_is_member,
)
from pages.components import pill

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
UNCHANGED = object()
HIDDEN = {"display": "none"}
SHOWN = {"display": "flex"}

_REGISTERED = False


def read_joined_ids() -> list[str]:
    try:
        raw = session.get("joined_ajo_ids") or []
    except RuntimeError:
        return []
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str) and item in GROUP_BY_ID]


def read_role(fallback: str | None) -> str | None:
    try:
        role = session.get("role")
    except RuntimeError:
        role = None
    if role in {"admin", "member"}:
        return role
    return fallback if fallback in {"admin", "member"} else None


def apply_join(group_id: str, role: str | None, joined_ids: list[str]) -> tuple[list[str], str]:
    group = group_by_id(group_id)
    updated = list(joined_ids)
    if group is None:
        return updated, "That circle is not available."
    if viewer_is_member(group, role, updated):
        return updated, f"You are already in {group['name']}."
    if not can_join(group, role, updated):
        return updated, f"{group['name']} is not open to new members."
    updated.append(group["id"])
    return updated, f"Join request sent for {group['name']}."


def invite_problem(email: object, message: object) -> str | None:
    if not isinstance(email, str) or not email.strip():
        return "Enter an email address."
    cleaned = email.strip()
    if len(cleaned) > 254 or EMAIL_RE.fullmatch(cleaned) is None:
        return "Enter a valid email address."
    if message is None:
        message = ""
    if not isinstance(message, str):
        return "The personal message is not valid."
    if len(message) > 500:
        return "Keep the personal message under 500 characters."
    return None


def dispatch_join_action(
    trigger: object,
    *,
    role: str | None,
    joined_ids: list[str],
    view_gid: str | None,
    invite_gid: str | None,
    manage_gid: str | None,
    email: object,
    message: object,
    rev: int,
) -> dict:
    """Pure UI transition for card actions and the invite dialog."""
    result = {
        "joined_ids": list(joined_ids),
        "rev": UNCHANGED,
        "notice": UNCHANGED,
        "view_gid": view_gid if view_gid in GROUP_BY_ID else None,
        "invite_gid": invite_gid if invite_gid in GROUP_BY_ID else None,
        "manage_gid": manage_gid if manage_gid in GROUP_BY_ID else None,
        "invite_error": UNCHANGED,
        "clear_form": False,
    }
    action, gid = _trigger_parts(trigger)
    if action == "view" and gid:
        result["view_gid"] = gid
        result["invite_gid"] = None
        result["manage_gid"] = None
        result["invite_error"] = ""
    elif action == "close-view":
        result["view_gid"] = None
    elif action == "join" and gid:
        updated, notice = apply_join(gid, role, result["joined_ids"])
        result["joined_ids"] = updated
        result["notice"] = notice
        if updated != list(joined_ids):
            result["rev"] = rev + 1
    elif action == "invite" and gid:
        result["invite_gid"] = gid
        result["view_gid"] = None
        result["manage_gid"] = None
        result["invite_error"] = ""
    elif action in {"close-invite", "cancel-invite"}:
        result["invite_gid"] = None
        result["invite_error"] = ""
    elif action == "send-invite":
        problem = invite_problem(email, message)
        if result["invite_gid"] is None:
            result["notice"] = "Choose a circle before sending an invitation."
        elif problem:
            result["invite_error"] = problem
        else:
            invited = str(email).strip()
            result["notice"] = f"Invitation queued for {invited}."
            result["invite_gid"] = None
            result["invite_error"] = ""
            result["clear_form"] = True
    elif action == "manage" and gid:
        group = group_by_id(gid)
        if group is not None and viewer_is_creator(group, role):
            result["manage_gid"] = gid
            result["view_gid"] = None
            result["invite_gid"] = None
        else:
            result["manage_gid"] = None
            result["notice"] = "Only the circle creator can manage members."
    elif action == "close-manage":
        result["manage_gid"] = None
    return result


def _trigger_parts(trigger: object) -> tuple[str | None, str | None]:
    if trigger == "join-view-close":
        return "close-view", None
    if trigger == "join-invite-close":
        return "close-invite", None
    if trigger == "join-invite-cancel":
        return "cancel-invite", None
    if trigger == "join-invite-send":
        return "send-invite", None
    if trigger == "join-manage-close":
        return "close-manage", None
    if isinstance(trigger, dict):
        kind = trigger.get("type")
        gid = trigger.get("gid")
        mapping = {
            "ajo-view": "view",
            "ajo-join": "join",
            "ajo-invite": "invite",
            "ajo-manage": "manage",
        }
        action = mapping.get(kind)
        if action and group_by_id(gid) is not None:
            return action, gid
    return None, None


def _money(amount: int) -> str:
    return f"£{amount:,}"


def _per(frequency: str) -> str:
    if frequency == "weekly":
        return "week"
    return "month"


def _end_label(iso_date: str) -> str:
    parsed = _parse_display_date(iso_date)
    return parsed.strftime("%b %Y") if parsed else iso_date


def _parse_display_date(iso_date: str):
    from datetime import date

    try:
        return date.fromisoformat(iso_date)
    except ValueError:
        return None


def _status_pill(status: str):
    label = {"active": "Active", "open": "Open", "completed": "Completed"}.get(status, status)
    style = {"active": "good", "open": "brand", "completed": "gold"}.get(status, "")
    return pill(label, style)


def _avatars(group: dict, role: str | None, joined_ids: list[str]):
    bubbles = []
    for initials, color in group["avatars"][:4]:
        bubbles.append(
            html.Span(initials, className="join-avatar", style={"background": color})
        )
    extra = displayed_member_count(group, role, joined_ids) - len(bubbles)
    if extra > 0:
        bubbles.append(html.Span(f"+{extra}", className="join-avatar more"))
    return html.Div(bubbles, className="join-avatars")


def _action_button(action: str, group_id: str):
    class_name = "btn btn-sm btn-ghost"
    if action == "join":
        class_name = "btn btn-sm btn-primary"
    elif action == "invite":
        class_name = "btn btn-sm join-btn-invite"
    elif action == "manage":
        class_name = "btn btn-sm join-btn-manage"
    return html.Button(
        ACTION_LABELS[action],
        id={"type": f"ajo-{action}", "gid": group_id},
        n_clicks=0,
        className=class_name,
        type="button",
    )


def group_card(group: dict, role: str | None, joined_ids: list[str]):
    count = displayed_member_count(group, role, joined_ids)
    actions = card_actions(group, role, joined_ids)
    return html.Div(
        id=f"ajo-card-{group['id']}",
        className="card join-card",
        children=[
            html.Div(
                className="join-card-top",
                children=[
                    html.Div(
                        [
                            html.H2(group["name"], className="join-card-title"),
                            html.Div(
                                [html.I(className="bi bi-people"), f"{count} members · {group['city']}"],
                                className="join-meta",
                            ),
                        ]
                    ),
                    _status_pill(group["status"]),
                ],
            ),
            html.Div(
                className="join-stats",
                children=[
                    _stat("Contribution", f"{_money(group['contribution'])} per {_per(group['frequency'])}"),
                    _stat("Total pool", _money(group["pool"])),
                    _stat("Your role", role_label(group, role, joined_ids)),
                    _stat("End date", _end_label(group["end"])),
                ],
            ),
            _avatars(group, role, joined_ids),
            html.Div(
                [_action_button(action, group["id"]) for action in actions],
                className="join-actions",
            ),
        ],
    )


def _stat(label: str, value: str):
    return html.Div([html.Div(label, className="join-stat-label"), html.Div(value, className="join-stat-value")])


def results_children(role: str | None, joined_ids: list[str], groups: list[dict]):
    if not groups:
        return [html.Div("No circles match this search.", className="card join-empty")]
    return [group_card(group, role, joined_ids) for group in groups]


def summary_text(shown: int, total: int) -> str:
    return f"Showing {shown} of {total} circles"


def view_body(group: dict, role: str | None, joined_ids: list[str]):
    count = displayed_member_count(group, role, joined_ids)
    places = max(int(group["capacity"]) - count, 0)
    return html.Div(
        [
            html.Div(className="join-card-top", children=[html.H2(group["name"], className="join-card-title"), _status_pill(group["status"])]),
            html.P(group["summary"], className="sub"),
            html.Div(
                className="join-stats",
                children=[
                    _stat("City", group["city"]),
                    _stat("Your role", role_label(group, role, joined_ids)),
                    _stat("Contribution", f"{_money(group['contribution'])} per {_per(group['frequency'])}"),
                    _stat("Total pool", _money(group["pool"])),
                    _stat("Members", f"{count} of {group['capacity']}"),
                    _stat("Places left", str(places)),
                    _stat("Starts", _end_label(group["start"])),
                    _stat("Ends", _end_label(group["end"])),
                ],
            ),
            html.P("Use the buttons on the card to join, invite, or manage members.", className="join-help"),
        ]
    )


def invite_summary(group: dict):
    return html.Div(
        className="join-group-box",
        children=[
            html.Div(f"Group: {group['name']}", className="join-group-name"),
            html.Div(
                f"{group['city']} · {_money(group['contribution'])} per {_per(group['frequency'])} · {group['member_count']} members",
                className="join-help",
            ),
        ],
    )


def manage_body(group: dict):
    rows = [
        html.Div(
            [html.Span(name), html.Span(member_role, className="pill")],
            className="join-roster-row",
        )
        for name, member_role in group["roster"]
    ]
    extra = int(group["member_count"]) - len(group["roster"])
    if extra > 0:
        rows.append(html.Div(f"+ {extra} more members", className="join-help"))
    return html.Div(
        [
            html.Div(className="join-group-box", children=[html.Div(group["name"], className="join-group-name"), html.Div(group["summary"], className="join-help")]),
            html.Div(rows, className="join-roster"),
        ]
    )


def layout(role: str | None):
    role = read_role(role)
    joined_ids = read_joined_ids()
    groups = filter_groups(role)
    return html.Div(
        id="join-page",
        className="stack",
        children=[
            html.Div(
                className="page-head",
                children=[
                    html.Div(
                        [
                            html.H1("Join Ajo"),
                            html.Div("Search circles, then view details or join.", className="sub"),
                        ]
                    )
                ],
            ),
            html.Div(id="join-notice"),
            html.Div(
                className="join-toolbar",
                children=[
                    html.Div(
                        className="join-field grow",
                        children=[
                            html.Div("Search", className="label-xs"),
                            dcc.Input(
                                id="join-search",
                                type="text",
                                placeholder="Search circles…",
                                value="",
                                n_submit=0,
                                className="join-input",
                                debounce=False,
                            ),
                        ],
                    ),
                    html.Button("Search", id="join-search-btn", n_clicks=0, className="btn btn-primary", type="button"),
                    html.Div(
                        className="join-field",
                        children=[
                            html.Div("Filter", className="label-xs"),
                            dcc.Dropdown(
                                id="join-filter",
                                options=[
                                    {"label": "All groups", "value": "all"},
                                    {"label": "Active", "value": "active"},
                                    {"label": "Completed", "value": "completed"},
                                    {"label": "Open to join", "value": "open"},
                                    {"label": "Groups I manage", "value": "managed"},
                                ],
                                value="all",
                                clearable=False,
                                searchable=False,
                                className="join-dropdown",
                            ),
                        ],
                    ),
                    html.Div(
                        className="join-field",
                        children=[
                            html.Div("Date range", className="label-xs"),
                            html.Div(
                                className="join-dates",
                                children=[
                                    dcc.Input(id="join-date-from", type="date", className="join-input", placeholder="From"),
                                    html.Span("to", className="muted"),
                                    dcc.Input(id="join-date-to", type="date", className="join-input", placeholder="To"),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(summary_text(len(groups), len(GROUPS)), id="join-summary", className="sub"),
            html.Div(results_children(role, joined_ids, groups), id="join-results", className="join-grid"),
            dcc.Store(id="join-rev", data=0),
            dcc.Store(id="join-view-gid", data=None),
            dcc.Store(id="join-invite-gid", data=None),
            dcc.Store(id="join-manage-gid", data=None),
            _view_modal(),
            _invite_modal(),
            _manage_modal(),
        ],
    )


def _view_modal():
    return html.Div(
        id="join-view-modal",
        className="join-modal-back",
        style=HIDDEN,
        children=[
            html.Div(
                className="join-modal",
                children=[
                    html.Div(
                        className="join-modal-hd",
                        children=[
                            html.H2("Circle details"),
                            html.Button("×", id="join-view-close", n_clicks=0, className="join-modal-x", type="button", **{"aria-label": "Close"}),
                        ],
                    ),
                    html.Div(id="join-view-body", className="join-modal-bd"),
                ],
            )
        ],
    )


def _invite_modal():
    return html.Div(
        id="join-invite-modal",
        className="join-modal-back",
        style=HIDDEN,
        children=[
            html.Div(
                className="join-modal",
                children=[
                    html.Div(
                        className="join-modal-hd",
                        children=[
                            html.H2("Invite Member to Group"),
                            html.Button("×", id="join-invite-close", n_clicks=0, className="join-modal-x", type="button", **{"aria-label": "Close"}),
                        ],
                    ),
                    html.Div(
                        className="join-modal-bd",
                        children=[
                            html.Div(id="join-invite-summary"),
                            html.Div(
                                [
                                    html.Label("Email Address *", htmlFor="join-invite-email", className="join-label"),
                                    dcc.Input(
                                        id="join-invite-email",
                                        type="email",
                                        placeholder="Enter the email address of the person to invite",
                                        value="",
                                        className="join-input",
                                    ),
                                ],
                                className="join-field",
                            ),
                            html.Div(
                                [
                                    html.Label("Personal Message (Optional)", htmlFor="join-invite-message", className="join-label"),
                                    dcc.Textarea(
                                        id="join-invite-message",
                                        placeholder="Add a personal message to your invitation...",
                                        value="",
                                        className="join-textarea",
                                    ),
                                    html.Div("This message will be included with the invitation link.", className="join-help"),
                                ],
                                className="join-field",
                            ),
                            html.Div(id="join-invite-error", className="join-error"),
                        ],
                    ),
                    html.Div(
                        className="join-modal-ft",
                        children=[
                            html.Button("Cancel", id="join-invite-cancel", n_clicks=0, className="btn join-btn-cancel", type="button"),
                            html.Button("Send Invitation", id="join-invite-send", n_clicks=0, className="btn btn-primary", type="button"),
                        ],
                    ),
                ],
            )
        ],
    )


def _manage_modal():
    return html.Div(
        id="join-manage-modal",
        className="join-modal-back",
        style=HIDDEN,
        children=[
            html.Div(
                className="join-modal",
                children=[
                    html.Div(
                        className="join-modal-hd",
                        children=[
                            html.H2("Circle members"),
                            html.Button("×", id="join-manage-close", n_clicks=0, className="join-modal-x", type="button", **{"aria-label": "Close"}),
                        ],
                    ),
                    html.Div(id="join-manage-body", className="join-modal-bd"),
                    html.Div(
                        className="join-modal-ft",
                        children=[html.Button("Close", id="join-manage-close-footer", n_clicks=0, className="btn btn-ghost", type="button")],
                    ),
                ],
            )
        ],
    )


def _clicked() -> bool:
    if not ctx.triggered:
        return False
    value = ctx.triggered[0].get("value")
    return isinstance(value, int) and value > 0


def _notice(text: object):
    if text is UNCHANGED:
        return no_update
    if not text:
        return []
    return html.Div(str(text), className="join-banner")


def register_join_callbacks(app) -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    _REGISTERED = True

    @app.callback(
        Output("join-results", "children"),
        Output("join-summary", "children"),
        Input("join-search-btn", "n_clicks"),
        Input("join-search", "n_submit"),
        Input("join-filter", "value"),
        Input("join-date-from", "value"),
        Input("join-date-to", "value"),
        Input("join-rev", "data"),
        State("join-search", "value"),
        prevent_initial_call=True,
    )
    def refresh_join(_search_clicks, _submit, status, date_from, date_to, _rev, search):
        role = read_role(None)
        if role is None:
            raise PreventUpdate
        trigger = ctx.triggered_id
        if trigger in {"join-search-btn", "join-search"} and not _clicked():
            raise PreventUpdate
        joined_ids = read_joined_ids()
        groups = filter_groups(role, search or "", status or "all", date_from, date_to)
        return results_children(role, joined_ids, groups), summary_text(len(groups), len(GROUPS))

    @app.callback(
        Output("join-rev", "data"),
        Output("join-notice", "children"),
        Output("join-view-modal", "style"),
        Output("join-view-body", "children"),
        Output("join-view-gid", "data"),
        Output("join-invite-modal", "style"),
        Output("join-invite-summary", "children"),
        Output("join-invite-error", "children"),
        Output("join-invite-gid", "data"),
        Output("join-invite-email", "value"),
        Output("join-invite-message", "value"),
        Output("join-manage-modal", "style"),
        Output("join-manage-body", "children"),
        Output("join-manage-gid", "data"),
        Input({"type": "ajo-view", "gid": ALL}, "n_clicks"),
        Input({"type": "ajo-join", "gid": ALL}, "n_clicks"),
        Input({"type": "ajo-invite", "gid": ALL}, "n_clicks"),
        Input({"type": "ajo-manage", "gid": ALL}, "n_clicks"),
        Input("join-view-close", "n_clicks"),
        Input("join-invite-close", "n_clicks"),
        Input("join-invite-cancel", "n_clicks"),
        Input("join-invite-send", "n_clicks"),
        Input("join-manage-close", "n_clicks"),
        Input("join-manage-close-footer", "n_clicks"),
        State("join-rev", "data"),
        State("join-view-gid", "data"),
        State("join-invite-gid", "data"),
        State("join-manage-gid", "data"),
        State("join-invite-email", "value"),
        State("join-invite-message", "value"),
        prevent_initial_call=True,
    )
    def on_join_action(_view, _join, _invite, _manage, _c1, _c2, _c3, _c4, _c5, _c6, rev, view_gid, invite_gid, manage_gid, email, message):
        if not _clicked():
            raise PreventUpdate
        role = read_role(None)
        if role is None:
            raise PreventUpdate
        trigger = ctx.triggered_id
        if trigger == "join-manage-close-footer":
            trigger = "join-manage-close"
        joined_ids = read_joined_ids()
        outcome = dispatch_join_action(
            trigger,
            role=role,
            joined_ids=joined_ids,
            view_gid=view_gid,
            invite_gid=invite_gid,
            manage_gid=manage_gid,
            email=email,
            message=message,
            rev=rev or 0,
        )
        if outcome["joined_ids"] != joined_ids:
            session["joined_ajo_ids"] = outcome["joined_ids"]
        view_group = group_by_id(outcome["view_gid"]) if outcome["view_gid"] else None
        invite_group = group_by_id(outcome["invite_gid"]) if outcome["invite_gid"] else None
        manage_group = group_by_id(outcome["manage_gid"]) if outcome["manage_gid"] else None
        return (
            outcome["rev"] if outcome["rev"] is not UNCHANGED else no_update,
            _notice(outcome["notice"]),
            SHOWN if view_group else HIDDEN,
            view_body(view_group, role, outcome["joined_ids"]) if view_group else [],
            outcome["view_gid"],
            SHOWN if invite_group else HIDDEN,
            invite_summary(invite_group) if invite_group else [],
            "" if outcome["invite_error"] is UNCHANGED else outcome["invite_error"],
            outcome["invite_gid"],
            "" if outcome["clear_form"] else no_update,
            "" if outcome["clear_form"] else no_update,
            SHOWN if manage_group else HIDDEN,
            manage_body(manage_group) if manage_group else [],
            outcome["manage_gid"],
        )
