"""My Ajo: the signed-in person's circles, in one card shape.

Membership comes from the synthetic persona file (#16). Local stub sign-in
(#20) chooses which persona is on screen: ``admintest`` is the admin persona,
and ``membertest`` is the first member who belongs to only one group.

When a group records ``created_by`` (#24, already on the persona file), that
persona is the admin of the Ajo. A group without ``created_by`` still renders;
the viewer's own persona role is used instead. Emails and passwords are never
copied onto a card.
"""

from __future__ import annotations

from pathlib import Path

from dash import html

from .components import pill
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


def ajos_for_viewer(document: dict, viewer: dict | None) -> list[dict]:
    """Public Ajo cards for one viewer. Safe when ``created_by`` is absent."""
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
        cards.append(
            {
                "name": name,
                "city": contribution["city"],
                "amount": amount,
                "frequency": contribution["frequency"],
                "member_count": len(members),
                "pot": amount * len(members),
                "viewer_is_admin": _is_admin(group, viewer, creator),
                "created_by": creator.get("id") if creator else None,
                "creator_name": creator.get("name") if creator else None,
                "members": members,
            }
        )
    return cards


def _money(amount: int) -> str:
    return f"£{amount:,}"


def _card(ajo: dict):
    role_label = "Admin" if ajo["viewer_is_admin"] else "Member"
    role_style = "brand" if ajo["viewer_is_admin"] else ""
    creator = ajo.get("creator_name")
    slug = ajo["name"].lower().replace(" ", "-")
    return html.Div(
        className="card my-ajo-card",
        id=f"my-ajo-card-{slug}",
        children=[
            html.Div(
                className="row-head",
                children=[
                    html.H2(ajo["name"], className="h2 my-ajo-name"),
                    pill(role_label, role_style),
                    pill("Verified", "good"),
                ],
            ),
            html.Div(
                f"{ajo['city']}  ·  {_money(ajo['amount'])} {ajo['frequency']}  ·  pot {_money(ajo['pot'])}",
                className="sub",
            ),
            html.Div(
                f"Created by {creator}" if creator else "Creator not recorded",
                className="sub my-ajo-creator",
            ) if creator else html.Div(className="my-ajo-creator"),
            html.Div(
                "You are the admin of this Ajo." if ajo["viewer_is_admin"] else "You are a member of this Ajo.",
                className="my-ajo-place",
            ),
            html.Div(f"{ajo['member_count']} members", className="label-xs my-ajo-count-label"),
            html.Div(
                className="my-ajo-members",
                children=[
                    html.Span(
                        className="my-ajo-member" + (" you" if member["is_viewer"] else ""),
                        children=[
                            member["name"],
                            html.Span("you", className="pill brand mini-pill") if member["is_viewer"] else None,
                            html.Span("creator", className="pill gold mini-pill") if member["is_creator"] else None,
                        ],
                    )
                    for member in ajo["members"]
                ],
            ),
        ],
    )


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
    viewer_name = viewer.get("name") if viewer else "this profile"
    count = len(cards)
    noun = "Ajo" if count == 1 else "Ajos"

    if error:
        body = html.Div(
            className="card",
            children=[
                html.Div("My Ajo is unavailable", className="h2"),
                html.Div("The local persona file could not be read.", className="sub"),
            ],
        )
    elif not cards:
        body = html.Div(
            className="card",
            id="my-ajo-empty",
            children=[
                html.Div("No Ajos yet", className="h2"),
                html.Div("This profile is not in an Ajo.", className="sub"),
            ],
        )
    else:
        body = html.Div(className="ajo-grid", children=[_card(ajo) for ajo in cards])

    return html.Div(
        className="stack",
        id="my-ajo",
        children=[
            html.Div(
                className="page-head",
                children=[
                    html.Div(
                        [
                            html.H1("My Ajo"),
                            html.Div(
                                f"{count} {noun} · viewing as {viewer_name}",
                                className="sub",
                                id="my-ajo-summary",
                            ),
                        ]
                    )
                ],
            ),
            body,
        ],
    )
