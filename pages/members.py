"""Members page: names and status for one Ajo at a time.

The signed-in role comes from the server session. Admin sees member
management for an Ajo they created. Members and admins share the Members,
Activity, and Communication tabs. The list does not include scores, emails,
or bank details.
"""

from __future__ import annotations

from dash import ALL, Input, Output, State, ctx, dcc, html, no_update

from .components import icon, status_pill
from .personas import (
    BRUM_BUILDERS,
    EXAMPLE_PERSONAS_PATH,
    GROUP_NAMES,
    SISTER_CIRCLE,
    load_personas,
)

ADMIN_PERSONA_ID = "persona-01"
MEMBER_PERSONA_ID = "persona-02"
TABS = ("members", "activity", "communication")
FILTERS = ("all", "paid", "pending", "received")
TAB_LABELS = {"members": "Members", "activity": "Activity", "communication": "Communication"}
JOINED = ("Sep 2024", "Sep 2024", "Oct 2024", "Oct 2024", "Nov 2024", "Nov 2024")
STATUS_BY_INDEX = ("received", "paid", "receiving", "paid", "paid", "pending", "paid", "received")
AVATAR_COLORS = ("#4F6AA3", "#4E5FA8", "#B88A2A", "#B0392E", "#4A89B0", "#7C5AA8", "#2F7A4C", "#7F6BB3", "#2A6E89")
AJO_DETAILS = {
    BRUM_BUILDERS: {
        "contribution": "£500.00",
        "frequency": "Monthly",
        "status": "Active",
        "capacity": 10,
        "duration": "10 months",
        "start": "28 Sep 2024",
        "end": "28 Jun 2025",
    },
    SISTER_CIRCLE: {
        "contribution": "£250.00",
        "frequency": "Monthly",
        "status": "Active",
        "capacity": 10,
        "duration": "10 months",
        "start": "1 Oct 2024",
        "end": "1 Jul 2025",
    },
}


def load_directory():
    """Personas for the member list. Fall back to the committed template."""
    try:
        return load_personas()
    except FileNotFoundError:
        return load_personas(EXAMPLE_PERSONAS_PATH)


def persona_for_session(role, username=None):
    """Map a server role to a fixture persona. The client cannot choose one.

    ``username`` is the signed-in account. It cannot grant the creator persona;
    only ``role == "admin"`` does.
    """
    if username == "admintest" and role != "admin":
        return MEMBER_PERSONA_ID
    if role == "admin":
        return ADMIN_PERSONA_ID
    return MEMBER_PERSONA_ID


def groups_for_persona(persona_id):
    document = load_directory()
    for persona in document["personas"]:
        if persona["id"] == persona_id:
            return [name for name in GROUP_NAMES if name in persona["groups"]]
    return [GROUP_NAMES[0]]


def resolve_ajo(persona_id, requested):
    allowed = groups_for_persona(persona_id)
    if requested in allowed:
        return requested
    return allowed[0]


def _username(persona):
    return str(persona["email"]).split("@", 1)[0]


def _initials(name):
    parts = [part for part in str(name).split() if part]
    letters = "".join(part[0] for part in parts[:2])
    return letters.upper() or "?"


def _avatar_color(key):
    return AVATAR_COLORS[sum(ord(char) for char in key) % len(AVATAR_COLORS)]


def member_rows(ajo_name, viewer_id=None):
    """Names, status, and rotation fields for one Ajo. No contact or bank data."""
    document = load_directory()
    people = [persona for persona in document["personas"] if ajo_name in persona["groups"]]
    people.sort(key=lambda persona: persona["id"])
    rows = []
    for index, persona in enumerate(people):
        status = STATUS_BY_INDEX[index % len(STATUS_BY_INDEX)]
        rows.append(
            {
                "id": persona["id"],
                "position": index + 1,
                "username": _username(persona),
                "name": persona["name"],
                "status": status,
                "on_time": "94%" if status == "pending" else "100%",
                "ajos": len(persona["groups"]),
                "joined": JOINED[index % len(JOINED)],
                "role": persona["role"],
                "you": persona["id"] == viewer_id,
                "next": status == "receiving",
                "color": _avatar_color(persona["id"]),
            }
        )
    return rows


def creator_name(ajo_name):
    document = load_directory()
    created_by = next(
        (group.get("created_by") for group in document["groups"] if group.get("name") == ajo_name),
        None,
    )
    for persona in document["personas"]:
        if persona["id"] == created_by:
            return persona["name"]
    return "Unknown"


def group_facts(ajo_name, total_members):
    meta = AJO_DETAILS.get(ajo_name) or {
        "contribution": "—",
        "frequency": "Monthly",
        "status": "Active",
        "capacity": max(total_members, 1),
        "duration": "—",
        "start": "—",
        "end": "—",
    }
    spots = max(int(meta["capacity"]) - total_members, 0)
    return {
        **meta,
        "members_label": f"{total_members}/{meta['capacity']}",
        "spots": spots,
        "creator": creator_name(ajo_name),
    }


def member_stats(rows):
    def count(predicate):
        return sum(1 for row in rows if predicate(row))

    return {
        "active": count(lambda row: row["status"] in {"received", "receiving", "paid"}),
        "pending": count(lambda row: row["status"] == "pending"),
        "suspended": 0,
        "admins": count(lambda row: row["role"] == "admin"),
        "total": len(rows),
        "recent": count(lambda row: row["status"] in {"paid", "receiving"}),
    }


def sort_rows(rows, sort_key):
    if sort_key == "name":
        return sorted(rows, key=lambda row: (row["name"].casefold(), row["position"]))
    return sorted(rows, key=lambda row: row["position"])


def filter_rows(rows, status_filter):
    if status_filter in {"paid", "pending", "received"}:
        return [row for row in rows if row["status"] == status_filter]
    return list(rows)


def members_csv(ajo_name, viewer_id=None):
    """Export names and status only."""
    lines = ["username,name,status"]
    for row in member_rows(ajo_name, viewer_id):
        lines.append(f"{row['username']},{row['name']},{row['status']}")
    return "\n".join(lines) + "\n"


def invite_message(raw, ajo_name):
    name = (raw or "").strip()
    if not name:
        return "Enter a username to queue an invite."
    if "@" in name or any(char.isspace() for char in name) or len(name) > 32:
        return "Use a single username. Email addresses are not collected here."
    if any(char in name for char in "\\/<>"):
        return "That username cannot be used."
    return f"Invite queued for @{name} to join {ajo_name}. Nothing is sent in this preview."


def _subtitle(count):
    noun = "member" if count == 1 else "members"
    return f"·  {count} credit-verified {noun} · usernames only"


def _filter_label(status, rows):
    counts = {
        "all": len(rows),
        "paid": sum(1 for row in rows if row["status"] == "paid"),
        "pending": sum(1 for row in rows if row["status"] == "pending"),
        "received": sum(1 for row in rows if row["status"] == "received"),
    }
    titles = {"all": "All", "paid": "Paid", "pending": "Pending", "received": "Received"}
    return f"{titles[status]} · {counts[status]}"


def _fact(label, value):
    return html.Div([html.Div(label, className="k"), html.Div(value, className="v")], className="ajo-fact")


def _stat(value, label, tone):
    return html.Div(
        [html.Div(str(value), className=f"n {tone}"), html.Div(label, className="l")],
        className="member-stat",
    )


def summary_panel(ajo_name, rows):
    facts = group_facts(ajo_name, len(rows))
    stats = member_stats(rows)
    spots = html.Span(
        f"{facts['spots']} available" if facts["spots"] else "Full",
        className="pill good" if facts["spots"] else "pill",
    )
    return html.Div(
        className="stack member-admin",
        children=[
            html.Div(
                className="card",
                children=[
                    html.Div(f"Ajo · {ajo_name}", className="h2"),
                    html.Div(
                        className="ajo-facts",
                        children=[
                            _fact("Contribution amount", facts["contribution"]),
                            _fact("Frequency", facts["frequency"]),
                            _fact("Status", html.Span(facts["status"], className="pill good")),
                            _fact("Members", facts["members_label"]),
                            _fact("Duration", facts["duration"]),
                            _fact("Available spots", spots),
                            _fact("Start date", facts["start"]),
                            _fact("End date", facts["end"]),
                            _fact("Created by", facts["creator"]),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="card",
                children=[
                    html.Div("Member statistics", className="h2"),
                    html.Div(
                        className="member-stats",
                        children=[
                            _stat(stats["active"], "Active", "good"),
                            _stat(stats["pending"], "Pending", "gold"),
                            _stat(stats["suspended"], "Suspended", "danger"),
                            _stat(stats["admins"], "Admins", "brand"),
                            _stat(stats["total"], "Total", ""),
                            _stat(stats["recent"], "Recent activity", "good"),
                        ],
                    ),
                ],
            ),
        ],
    )


def _member_cell(row):
    badges = []
    if row["next"]:
        badges.append(html.Span("next", className="pill gold mini-pill"))
    if row["you"]:
        badges.append(html.Span("you", className="pill brand mini-pill"))
    return html.Td(
        html.Div(
            className="member-row",
            children=[
                html.Div(_initials(row["name"]), className="mav", style={"background": row["color"]}),
                html.Div(
                    [
                        html.Div(
                            [html.Span(f"@{row['username']}", className="member-tag"), *badges],
                            className="member-top",
                        ),
                        html.Div(row["name"], className="meta-sub"),
                    ]
                ),
            ],
        )
    )


def members_table(rows):
    if not rows:
        return html.Div("No members in this view.", className="card members-empty")
    return html.Div(
        className="card members-card",
        children=[
            html.Table(
                className="t",
                children=[
                    html.Thead(
                        html.Tr(
                            [
                                html.Th("#", style={"width": "42px"}),
                                html.Th("Member"),
                                html.Th("Status"),
                                html.Th("On-time"),
                                html.Th("Ajos"),
                                html.Th("Joined"),
                            ]
                        )
                    ),
                    html.Tbody(
                        [
                            html.Tr(
                                [
                                    html.Td(row["position"], className="mono muted"),
                                    _member_cell(row),
                                    html.Td(status_pill(row["status"])),
                                    html.Td(row["on_time"], className="mono"),
                                    html.Td(row["ajos"], className="mono"),
                                    html.Td(row["joined"], className="muted"),
                                ]
                            )
                            for row in rows
                        ]
                    ),
                ],
            )
        ],
    )


def activity_panel(ajo_name, rows):
    return html.Div(
        className="card",
        children=[
            html.Div("Activity", className="h2"),
            html.Div(f"Recent contribution status in {ajo_name}. Names and status only.", className="meta-sub member-note"),
            html.Div(
                className="member-feed",
                children=[
                    html.Div(
                        className="member-feed-row",
                        children=[
                            html.Div(_initials(row["name"]), className="mav", style={"background": row["color"]}),
                            html.Div(
                                [
                                    html.Div(row["name"], className="meta-main"),
                                    html.Div(f"@{row['username']}", className="meta-sub"),
                                ]
                            ),
                            status_pill(row["status"]),
                        ],
                    )
                    for row in rows
                ],
            ),
        ],
    )


def communication_panel(ajo_name):
    notes = [
        (f"{ajo_name} contribution window", "Contributions for this cycle are collected from members of this Ajo."),
        ("Privacy", "Messages stay inside the Ajo. Members see names and status only."),
        ("Preview", "This preview does not send email or SMS."),
    ]
    return html.Div(
        className="card",
        children=[
            html.Div("Communication", className="h2"),
            html.Div(
                className="member-feed",
                children=[
                    html.Div(
                        className="member-feed-row member-note-row",
                        children=[
                            html.Div([html.Div(title, className="meta-main"), html.Div(body, className="meta-sub")])
                        ],
                    )
                    for title, body in notes
                ],
            ),
        ],
    )


def positions_panel(ajo_name, viewer_id):
    rows = member_rows(ajo_name, viewer_id)
    return html.Div(
        [
            html.Div("Rotation order", className="h2"),
            html.Div("Names and positions only. Changes are not saved in this preview.", className="meta-sub member-note"),
            html.Ol(
                [html.Li(f"#{row['position']}  {row['name']}") for row in rows],
                className="member-positions",
            ),
        ]
    )


def compose_view(role, username, requested_ajo, tab, status_filter, sort_key):
    """Build the pieces the Members callback swaps in. Role is the server role."""
    if role != "admin":
        role = "member"
    viewer_id = persona_for_session(role, username)
    ajo_name = resolve_ajo(viewer_id, requested_ajo)
    if tab not in TABS:
        tab = "members"
    if status_filter not in FILTERS:
        status_filter = "all"
    rows = member_rows(ajo_name, viewer_id)
    visible = filter_rows(sort_rows(rows, sort_key), status_filter if tab == "members" else "all")
    if tab == "activity":
        panel = activity_panel(ajo_name, sort_rows(rows, "pos"))
    elif tab == "communication":
        panel = communication_panel(ajo_name)
    else:
        panel = members_table(visible)
    summary = summary_panel(ajo_name, rows) if role == "admin" else html.Div()
    summary_style = {} if role == "admin" else {"display": "none"}
    return {
        "subtitle": _subtitle(len(rows)),
        "summary": summary,
        "summary_style": summary_style,
        "panel": panel,
        "tab_classes": ["on" if name == tab else "" for name in TABS],
        "filter_labels": [_filter_label(name, rows) for name in FILTERS],
        "filter_classes": ["on" if name == status_filter else "" for name in FILTERS],
        "tools_style": {} if tab == "members" else {"display": "none"},
        "ui": {"tab": tab, "filter": status_filter},
    }


def _reduce_ui(trigger, ui):
    state = ui if isinstance(ui, dict) else {}
    tab = state.get("tab") if state.get("tab") in TABS else "members"
    status_filter = state.get("filter") if state.get("filter") in FILTERS else "all"
    if isinstance(trigger, dict) and trigger.get("type") == "members-tab" and trigger.get("tab") in TABS:
        tab = trigger["tab"]
    elif isinstance(trigger, dict) and trigger.get("type") == "members-filter" and trigger.get("status") in FILTERS:
        status_filter = trigger["status"]
    elif trigger == "members-ajo":
        status_filter = "all"
    return tab, status_filter


def layout(role=None, username=None):
    viewer_role = "admin" if role == "admin" else "member"
    viewer_id = persona_for_session(viewer_role, username)
    groups = groups_for_persona(viewer_id)
    selected = groups[0]
    view = compose_view(viewer_role, username, selected, "members", "all", "pos")
    admin_tools = []
    if viewer_role == "admin":
        admin_tools = [
            html.Div(
                className="member-quick",
                children=[
                    html.Div("Quick actions", className="member-kicker"),
                    html.Div(
                        className="row-btns",
                        children=[
                            html.Button(
                                "Manage positions",
                                id="members-positions-btn",
                                n_clicks=0,
                                className="btn btn-primary btn-sm",
                            ),
                            html.Button(
                                [icon("dl"), "Export member list"],
                                id={"type": "members-export", "kind": "list"},
                                n_clicks=0,
                                className="btn btn-ghost btn-sm",
                            ),
                            html.Button(
                                "Refresh data",
                                id="members-refresh-btn",
                                n_clicks=0,
                                className="btn btn-ghost btn-sm",
                            ),
                        ],
                    ),
                    html.Div(id="members-notice", className="meta-sub member-note"),
                    html.Div(id="members-positions", style={"display": "none"}, className="card member-drawer"),
                    html.Div(
                        id="members-invite",
                        style={"display": "none"},
                        className="card member-drawer",
                        children=[
                            html.Div("Invite member", className="h2"),
                            html.Div("Username only. No email or phone is collected.", className="meta-sub member-note"),
                            html.Div(
                                className="row-btns",
                                children=[
                                    dcc.Input(
                                        id="members-invite-name",
                                        type="text",
                                        value="",
                                        placeholder="Username",
                                        maxLength=32,
                                        className="inp inp-sm",
                                        debounce=True,
                                    ),
                                    html.Button(
                                        "Queue invite",
                                        id="members-invite-send",
                                        n_clicks=0,
                                        className="btn btn-primary btn-sm",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            )
        ]
    header_actions = []
    if viewer_role == "admin":
        header_actions = [
            html.Button(
                "Back to My Ajo",
                id={"type": "nav-btn", "page": "circle"},
                n_clicks=0,
                className="btn btn-ghost",
            ),
            html.Button(
                [icon("plus"), "Invite member"],
                id="members-invite-open",
                n_clicks=0,
                className="btn btn-primary",
            ),
        ]
    return html.Div(
        id="members-page",
        className="stack",
        children=[
            dcc.Store(id="members-ui", data={"tab": "members", "filter": "all"}),
            dcc.Download(id="members-download"),
            html.Div(
                className="page-head",
                children=[
                    html.Div(
                        [
                            html.H1("Members"),
                            html.Div(
                                className="ajo-sub",
                                children=[
                                    html.Label("Ajo", htmlFor="members-ajo", className="member-kicker"),
                                    dcc.Dropdown(
                                        id="members-ajo",
                                        options=[{"label": name, "value": name} for name in groups],
                                        value=selected,
                                        clearable=False,
                                        searchable=False,
                                        className="ajo-dropdown",
                                    ),
                                    html.Span(view["subtitle"], id="members-subtitle", className="sub"),
                                ],
                            ),
                        ]
                    ),
                    html.Div(header_actions, className="row-btns head-actions"),
                ],
            ),
            *admin_tools,
            html.Div(view["summary"], id="members-summary", style=view["summary_style"]),
            html.Div(
                className="tabs member-tabs",
                children=[
                    html.Button(
                        TAB_LABELS[name],
                        id={"type": "members-tab", "tab": name},
                        n_clicks=0,
                        className="on" if name == "members" else "",
                    )
                    for name in TABS
                ],
            ),
            html.Div(
                id="members-tools",
                className="between members-controls",
                children=[
                    html.Div(
                        className="tabs",
                        children=[
                            html.Button(
                                view["filter_labels"][index],
                                id={"type": "members-filter", "status": name},
                                n_clicks=0,
                                className="on" if name == "all" else "",
                            )
                            for index, name in enumerate(FILTERS)
                        ],
                    ),
                    html.Div(
                        className="row-btns members-tools",
                        children=[
                            dcc.Dropdown(
                                id="members-sort",
                                options=[
                                    {"label": "Sort: Rotation position", "value": "pos"},
                                    {"label": "Sort: Name", "value": "name"},
                                ],
                                value="pos",
                                clearable=False,
                                searchable=False,
                                className="ajo-dropdown ajo-dropdown-sm",
                            ),
                            html.Button(
                                [icon("dl"), "CSV"],
                                id={"type": "members-export", "kind": "csv"},
                                n_clicks=0,
                                className="btn btn-ghost btn-sm",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(view["panel"], id="members-panel"),
        ],
    )


def register_callbacks(app):
    @app.callback(
        Output("members-subtitle", "children"),
        Output("members-summary", "children"),
        Output("members-summary", "style"),
        Output("members-panel", "children"),
        Output({"type": "members-tab", "tab": ALL}, "className"),
        Output({"type": "members-filter", "status": ALL}, "children"),
        Output({"type": "members-filter", "status": ALL}, "className"),
        Output("members-tools", "style"),
        Output("members-ui", "data"),
        Input("members-ajo", "value"),
        Input({"type": "members-tab", "tab": ALL}, "n_clicks"),
        Input({"type": "members-filter", "status": ALL}, "n_clicks"),
        Input("members-sort", "value"),
        State("members-ui", "data"),
        prevent_initial_call=True,
    )
    def update_members_view(ajo_value, _tabs, _filters, sort_key, ui):
        from flask import session

        role = session.get("role")
        username = session.get("username")
        tab, status_filter = _reduce_ui(ctx.triggered_id, ui)
        view = compose_view(role, username, ajo_value, tab, status_filter, sort_key or "pos")
        return (
            view["subtitle"],
            view["summary"],
            view["summary_style"],
            view["panel"],
            view["tab_classes"],
            view["filter_labels"],
            view["filter_classes"],
            view["tools_style"],
            view["ui"],
        )

    @app.callback(
        Output("members-download", "data"),
        Input({"type": "members-export", "kind": ALL}, "n_clicks"),
        State("members-ajo", "value"),
        prevent_initial_call=True,
    )
    def download_members(_clicks, ajo_value):
        from flask import session

        triggered = ctx.triggered[0]["value"] if ctx.triggered else None
        if not triggered:
            return no_update
        role = session.get("role")
        username = session.get("username")
        viewer_id = persona_for_session(role, username)
        ajo_name = resolve_ajo(viewer_id, ajo_value)
        slug = ajo_name.lower().replace(" ", "-")
        return dict(content=members_csv(ajo_name, viewer_id), filename=f"{slug}-members.csv", type="text/csv")

    @app.callback(
        Output("members-positions", "style"),
        Output("members-positions", "children"),
        Output("members-invite", "style"),
        Output("members-notice", "children"),
        Input("members-positions-btn", "n_clicks"),
        Input("members-invite-open", "n_clicks"),
        Input("members-refresh-btn", "n_clicks"),
        Input("members-invite-send", "n_clicks"),
        State("members-ajo", "value"),
        State("members-invite-name", "value"),
        State("members-positions", "style"),
        State("members-invite", "style"),
        prevent_initial_call=True,
    )
    def update_admin_tools(_positions, _invite, _refresh, _send, ajo_value, invite_name, positions_style, invite_style):
        from flask import session

        if session.get("role") != "admin":
            return no_update, no_update, no_update, no_update
        trigger = ctx.triggered_id
        viewer_id = persona_for_session("admin", session.get("username"))
        ajo_name = resolve_ajo(viewer_id, ajo_value)
        positions_style = positions_style or {"display": "none"}
        invite_style = invite_style or {"display": "none"}
        if trigger == "members-positions-btn":
            opening = positions_style.get("display") == "none"
            return (
                {} if opening else {"display": "none"},
                positions_panel(ajo_name, viewer_id) if opening else no_update,
                invite_style,
                "",
            )
        if trigger == "members-invite-open":
            opening = invite_style.get("display") == "none"
            return positions_style, no_update, {} if opening else {"display": "none"}, ""
        if trigger == "members-refresh-btn":
            return {"display": "none"}, no_update, {"display": "none"}, "Member list refreshed."
        if trigger == "members-invite-send":
            return positions_style, no_update, {}, invite_message(invite_name, ajo_name)
        return no_update, no_update, no_update, no_update
