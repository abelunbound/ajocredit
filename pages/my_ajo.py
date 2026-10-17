"""My Ajo: the original rotation screen for the signed-in person's circles.

Membership comes from the synthetic persona file. Local stub sign-in chooses
which persona is on screen: ``admintest`` is the admin persona, and
``membertest`` is the first member who belongs to only one group.

When that persona is in more than one Ajo, group tabs (the same control
Payouts Tracker uses) switch the whole screen. Emails and passwords are
never copied onto the page.
"""

from __future__ import annotations

from pathlib import Path

from dash import ALL, Input, Output, State, ctx, dcc, html
from flask import session

from .components import icon, pill
from .data import CIRCLE
from .personas import (
    DEFAULT_PERSONAS_PATH,
    EXAMPLE_PERSONAS_PATH,
    load_personas,
)

# Display-only contribution figures. The same fields are filled for every Ajo.
# Counts and the pot come from the persona membership, not from these numbers.
CONTRIBUTION = {
    "Brum Builders": {"city": "Birmingham, UK", "amount": 500, "frequency": "monthly"},
    "Sister Circle Ajo": {"city": "Birmingham, UK", "amount": 250, "frequency": "monthly"},
}
DEFAULT_CONTRIBUTION = {"city": "UK", "amount": 100, "frequency": "monthly"}

# The demo cycle is month 3, matching the original Brum Builders screen.
# A shorter circle highlights its last month instead.
CURRENT_MONTH = 3
PAYOUT_DATE = CIRCLE["next_date"]
MIN_CREDIT_SCORE = 680
AVATAR_COLORS = (
    "#4F6AA3",
    "#4E5FA8",
    "#B88A2A",
    "#B0392E",
    "#4A89B0",
    "#7C5AA8",
    "#2F7A4C",
    "#7F6BB3",
    "#2A6E89",
)

# Stub accounts are not rows in the persona file. These ids are the people
# each local login is viewing as.
STUB_VIEWERS = {
    "admintest": "persona-01",
    "membertest": "persona-06",
}


def load_ajo_document(path: Path | str | None = None) -> dict:
    """Load personas for My Ajo.

    Defaults to the git-ignored local file when it exists, and to the
    committed example otherwise.
    """
    if path is None:
        source = DEFAULT_PERSONAS_PATH if DEFAULT_PERSONAS_PATH.is_file() else EXAMPLE_PERSONAS_PATH
    else:
        source = Path(path)
    return load_personas(source)


def _personas(document: dict) -> list[dict]:
    personas = document.get("personas") if isinstance(document, dict) else None
    if not isinstance(personas, list):
        return []
    return [persona for persona in personas if isinstance(persona, dict) and persona.get("id")]


def _groups(document: dict) -> list[dict]:
    groups = document.get("groups") if isinstance(document, dict) else None
    if not isinstance(groups, list):
        return []
    return [group for group in groups if isinstance(group, dict) and group.get("name")]


def resolve_viewer(document: dict, username: str | None, role: str | None) -> dict | None:
    """Pick the persona My Ajo is showing. Stub usernames win over the role."""
    personas = _personas(document)
    by_id = {persona["id"]: persona for persona in personas}
    if username in STUB_VIEWERS and STUB_VIEWERS[username] in by_id:
        return by_id[STUB_VIEWERS[username]]

    if role == "admin":
        for persona in personas:
            if persona.get("role") == "admin":
                return persona
    for persona in personas:
        groups = persona.get("groups") or []
        if persona.get("role") == "member" and len(groups) == 1:
            return persona
    for persona in personas:
        if persona.get("role") == "member":
            return persona
    return personas[0] if personas else None


def _creator(group: dict, by_id: dict[str, dict]) -> dict | None:
    created_by = group.get("created_by")
    if not isinstance(created_by, str) or not created_by:
        return None
    return by_id.get(created_by)


def _is_admin(group: dict, viewer: dict, creator: dict | None) -> bool:
    if creator is not None:
        return viewer.get("id") == creator.get("id")
    return viewer.get("role") == "admin"


def _initials(name: str) -> str:
    parts = [part for part in str(name).split() if part]
    letters = "".join(part[0] for part in parts[:2])
    return letters.upper() or "?"


def _handle(name: str) -> str:
    """Short public tag. This is not an email address."""
    parts = [part for part in str(name).split() if part]
    if not parts:
        return "@member"
    if len(parts) == 1:
        return f"@{parts[0].lower()}"
    return f"@{parts[0].lower()}_{parts[-1][0].lower()}"


def _money(amount: int) -> str:
    return f"£{amount:,}"


def _timeline(members: list[dict]) -> list[dict]:
    size = len(members)
    current = min(CURRENT_MONTH, size) if size else 0
    rows = []
    for index, member in enumerate(members, start=1):
        if current and index < current:
            state = "received"
            detail = "received"
        elif index == current:
            state = "now"
            detail = PAYOUT_DATE
        else:
            state = "upcoming"
            detail = "upcoming"
        rows.append(
            {
                **member,
                "position": index,
                "state": state,
                "detail": detail,
                "initials": _initials(member["name"]),
                "color": AVATAR_COLORS[(index - 1) % len(AVATAR_COLORS)],
                "handle": _handle(member["name"]),
            }
        )
    return rows


def _cover_row(rows: list[dict]) -> dict | None:
    """One missed contribution, matching the original progress note."""
    if len(rows) < 2:
        return None
    for row in reversed(rows):
        if row["state"] != "now":
            return row
    return None


def ajos_for_viewer(document: dict, viewer: dict | None) -> list[dict]:
    """Public Ajo screens for one viewer. Safe when ``created_by`` is absent."""
    if not viewer:
        return []
    by_id = {persona["id"]: persona for persona in _personas(document)}
    membership = set(viewer.get("groups") or [])
    cards = []
    for group in _groups(document):
        name = group["name"]
        if name not in membership:
            continue
        creator = _creator(group, by_id)
        members = []
        for persona in _personas(document):
            if name not in (persona.get("groups") or []):
                continue
            members.append(
                {
                    "id": persona["id"],
                    "name": persona.get("name") or persona["id"],
                    "is_viewer": persona["id"] == viewer.get("id"),
                    "is_creator": creator is not None and persona["id"] == creator.get("id"),
                }
            )
        contribution = CONTRIBUTION.get(name, DEFAULT_CONTRIBUTION)
        amount = contribution["amount"]
        rows = _timeline(members)
        cover = _cover_row(rows)
        size = len(members)
        collected_count = size - (1 if cover else 0)
        current = min(CURRENT_MONTH, size) if size else 0
        cards.append(
            {
                "name": name,
                "city": contribution["city"],
                "amount": amount,
                "frequency": contribution["frequency"],
                "member_count": size,
                "pot": amount * size,
                "month": current,
                "collected_count": collected_count,
                "collected_amount": amount * collected_count,
                "cover_handle": cover["handle"] if cover else None,
                "cover_amount": amount if cover else 0,
                "viewer_is_admin": _is_admin(group, viewer, creator),
                "created_by": creator.get("id") if creator else None,
                "creator_name": creator.get("name") if creator else None,
                "members": members,
                "rows": rows,
            }
        )
    return cards


def _safe_document() -> dict:
    try:
        return load_ajo_document()
    except (OSError, ValueError):
        return {}


def resolve_ajo_name(requested: str | None, username: str | None, role: str | None, document: dict | None = None) -> str | None:
    """Return a group this viewer belongs to. Unknown names fall back to the first."""
    loaded = document if document is not None else _safe_document()
    names = [card["name"] for card in ajos_for_viewer(loaded, resolve_viewer(loaded, username, role))]
    if not names:
        return None
    if requested in names:
        return requested
    return names[0]


def ajo_switch(names: list[str], selected: str | None):
    return html.Div(
        className="tabs",
        id="my-ajo-switch",
        children=[
            html.Button(
                name,
                id={"type": "my-ajo-btn", "name": name},
                n_clicks=0,
                className="on" if name == selected else "",
            )
            for name in names
        ],
    )


def _header(ajo: dict):
    size = ajo["member_count"]
    subtitle = (
        f"{ajo['city']} · {_money(ajo['amount'])} x {size} {ajo['frequency']} · pot {_money(ajo['pot'])}"
    )
    return html.Div(
        className="page-head",
        children=[
            html.Div(
                [
                    html.Div(
                        [
                            html.H1(ajo["name"], id="my-ajo-title"),
                            html.Span(
                                [icon("shield"), "Verified"],
                                className="pill good my-ajo-verified",
                            ),
                            pill(f"Month {ajo['month']}/{size}", "brand"),
                        ],
                        className="row-head my-ajo-title",
                    ),
                    html.Div(subtitle, className="sub", id="my-ajo-subtitle"),
                ]
            )
        ],
    )


def _timeline_card(ajo: dict):
    pot = _money(ajo["pot"])
    return html.Div(
        className="card",
        children=[
            html.Div("Rotation timeline", className="h2"),
            html.Div(
                className="circle-timeline",
                id="my-ajo-timeline",
                children=[
                    html.Div(
                        className=f"tl-item {row['state']}",
                        children=[
                            html.Span(className="tl-dot"),
                            html.Div(
                                className="tl-row",
                                children=[
                                    html.Div(
                                        row["initials"],
                                        className="tl-av",
                                        style={"background": row["color"]},
                                    ),
                                    html.Div(
                                        className="tl-main",
                                        children=[
                                            html.Div(
                                                [
                                                    html.Span(row["name"]),
                                                    html.Span("you", className="pill brand tl-you")
                                                    if row["is_viewer"]
                                                    else None,
                                                ],
                                                className="tl-name",
                                            ),
                                            html.Div(
                                                f"Month {row['position']} · {row['detail']}",
                                                className="tl-sub",
                                            ),
                                        ],
                                    ),
                                    html.Div(pot, className="mono tl-amt"),
                                ],
                            ),
                        ],
                    )
                    for row in ajo["rows"]
                ],
            ),
        ],
    )


def _rules_card(ajo: dict):
    rules = (
        ("Contribution", f"{_money(ajo['amount'])} {ajo['frequency']} · autopay 1st"),
        ("Rotation", "Fixed by join-date"),
        ("Late grace", "48 hours"),
        ("Exit", "Only after payout month"),
        ("Min credit score", str(MIN_CREDIT_SCORE)),
    )
    return html.Div(
        className="card",
        children=[
            html.Div("Circle rules", className="h2"),
            html.Div(
                className="rules-list",
                children=[
                    html.Div(
                        [
                            html.Div(label, className="label-xs"),
                            html.Div(value, className="rule-val"),
                        ],
                        className="rule-item",
                    )
                    for label, value in rules
                ],
            ),
        ],
    )


def _progress_card(ajo: dict):
    size = ajo["member_count"] or 1
    width = f"{(ajo['collected_count'] / size) * 100:.4g}%"
    note = None
    if ajo.get("cover_handle"):
        note = html.Div(
            className="prog-note",
            children=[
                icon("bolt"),
                html.Span(
                    f"Delay Cover covering {_money(ajo['cover_amount'])} for {ajo['cover_handle']}"
                ),
            ],
        )
    return html.Div(
        className="card",
        children=[
            html.Div("Contribution progress", className="h2"),
            html.Div(
                className="between prog-meta",
                children=[
                    html.Span(f"{ajo['collected_count']} of {ajo['member_count']} collected"),
                    html.Span(
                        f"{_money(ajo['collected_amount'])} / {_money(ajo['pot'])}",
                        className="mono",
                    ),
                ],
            ),
            html.Div(className="bar prog-bar", children=[html.Span(style={"width": width})]),
            note,
        ],
    )


def ajo_body(ajo: dict):
    """Header, rotation timeline, rules, and progress for one Ajo."""
    return [
        _header(ajo),
        html.Div(
            className="g3-1",
            children=[
                _timeline_card(ajo),
                html.Div(
                    className="stack",
                    children=[_rules_card(ajo), _progress_card(ajo)],
                ),
            ],
        ),
    ]


def _empty_body():
    return html.Div(
        className="card",
        id="my-ajo-empty",
        children=[
            html.Div("No Ajos yet", className="h2"),
            html.Div("This profile is not in an Ajo.", className="sub"),
        ],
    )


def _unavailable_body():
    return html.Div(
        className="card",
        children=[
            html.Div("My Ajo is unavailable", className="h2"),
            html.Div("The local persona file could not be read.", className="sub"),
        ],
    )


def _tab_classes(selected: str | None) -> list[str]:
    specs = ctx.outputs_list[-1] if ctx.outputs_list else []
    if not isinstance(specs, list):
        return []
    classes = []
    for spec in specs:
        ident = spec.get("id") if isinstance(spec, dict) else None
        name = ident.get("name") if isinstance(ident, dict) else None
        classes.append("on" if name and name == selected else "")
    return classes


def layout(role: str | None, username: str | None = None, document: dict | None = None):
    """Render My Ajo. ``document`` is optional so tests can pass a fixture."""
    loaded = document
    error = None
    if loaded is None:
        try:
            loaded = load_ajo_document()
        except (OSError, ValueError) as exc:
            error = str(exc)
            loaded = {}

    viewer = resolve_viewer(loaded, username, role)
    cards = ajos_for_viewer(loaded, viewer)
    if error:
        body = _unavailable_body()
        switch = None
        store = None
    elif not cards:
        body = _empty_body()
        switch = None
        store = None
    else:
        selected = cards[0]["name"]
        store = dcc.Store(id="my-ajo-selected", data=selected)
        switch = ajo_switch([card["name"] for card in cards], selected)
        body = html.Div(id="my-ajo-body", children=ajo_body(cards[0]))

    return html.Div(
        className="stack",
        id="my-ajo",
        children=[child for child in (store, switch, body) if child is not None],
    )


def register_callbacks(app) -> None:
    @app.callback(
        Output("my-ajo-selected", "data"),
        Input({"type": "my-ajo-btn", "name": ALL}, "n_clicks"),
        State("my-ajo-selected", "data"),
        prevent_initial_call=True,
    )
    def select_my_ajo(_clicks, current):
        username = session.get("username")
        role = session.get("role")
        trig = ctx.triggered_id
        requested = trig.get("name") if isinstance(trig, dict) and trig.get("type") == "my-ajo-btn" else current
        return resolve_ajo_name(requested, username, role)

    @app.callback(
        Output("my-ajo-body", "children"),
        Output({"type": "my-ajo-btn", "name": ALL}, "className"),
        Input("my-ajo-selected", "data"),
    )
    def render_my_ajo_selection(ajo_name):
        username = session.get("username")
        role = session.get("role")
        document = _safe_document()
        allowed = resolve_ajo_name(ajo_name, username, role, document)
        classes = _tab_classes(allowed)
        if allowed is None:
            return _empty_body(), classes
        viewer = resolve_viewer(document, username, role)
        card = next(card for card in ajos_for_viewer(document, viewer) if card["name"] == allowed)
        return ajo_body(card), classes
