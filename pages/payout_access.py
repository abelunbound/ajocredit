"""Who may see an Ajo's Payouts Tracker.

The creator of an Ajo is the admin of that Ajo. The local stub ``admintest``
is that creator. Everyone else, including ``membertest``, sees no tracker.
The #20 role gate still applies: a member session is never treated as admin.
"""

from __future__ import annotations

import dash_api
from pages.personas import EXAMPLE_PERSONAS_PATH, load_personas

CREATOR_STUB = "admintest"


def load_circle_document():
    """Persona document that records each Ajo and its creator.

    The git-ignored local file wins when it exists. Otherwise the committed
    example is used so the tracker still has dummy circles.
    """
    try:
        return load_personas()
    except FileNotFoundError:
        return load_personas(EXAMPLE_PERSONAS_PATH)


def _api_admin_names() -> list[str] | None:
    """Admin circle names from the API session, or None when this is the stub."""
    try:
        from flask import has_request_context, session
    except ImportError:
        return None
    if not has_request_context() or not session.get("api_sid"):
        return None
    if dash_api.service_unavailable():
        return []
    circles = session.get("circles") or []
    names: list[str] = []
    for circle in circles:
        if not isinstance(circle, dict) or circle.get("role") != "admin":
            continue
        name = circle.get("name")
        if isinstance(name, str) and name and name not in names:
            names.append(name)
    return names


def visible_ajo_names(username, role, document=None) -> list[str]:
    """Return Ajo names whose Payouts Tracker this session may see.

    An API session uses the circle role the server returned. The stub path
    still requires the server role admin and the creator stub ``admintest``.
    """
    api_names = _api_admin_names()
    if api_names is not None:
        return api_names
    if role != "admin" or username != CREATOR_STUB:
        return []
    document = load_circle_document() if document is None else document
    creator_ids = {
        persona.get("id")
        for persona in document.get("personas", [])
        if isinstance(persona, dict) and persona.get("role") == "admin"
    }
    names: list[str] = []
    for group in document.get("groups", []):
        if not isinstance(group, dict) or group.get("created_by") not in creator_ids:
            continue
        name = group.get("name")
        if isinstance(name, str) and name and name not in names:
            names.append(name)
    return names


def resolve_ajo(requested, username, role, document=None) -> str | None:
    """Pick the Ajo tracker to render. Ignore a name this user did not create."""
    allowed = visible_ajo_names(username, role, document)
    if not allowed:
        return None
    if requested in allowed:
        return requested
    return allowed[0]
