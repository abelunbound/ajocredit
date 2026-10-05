"""Sidebar "My circles" list, loaded from dummy data until a database exists.

Circle names come from the persona groups document (#16). Create circle and
Join Ajo come from ``data/circle_actions.json``. Swap the loaders for a
database query later; the sidebar should keep calling ``my_circles_rows``.
"""

from __future__ import annotations

import json
from pathlib import Path

from dash import html

from pages.components import ICONS, icon
from pages.personas import EXAMPLE_PERSONAS_PATH, load_personas

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ACTIONS_PATH = REPO_ROOT / "data" / "circle_actions.json"

# Join Ajo sits directly under Create circle. Ids are stable; labels live in the file.
ACTION_ORDER = ("create-circle", "join-ajo")


def load_circle_names(path: Path | str | None = None) -> list[str]:
    """Return group names in persona-document order.

    ``path`` defaults to the git-ignored personas file. When that file has
    not been copied yet, the committed example template is used so the
    sidebar still renders.
    """
    document = _persona_document(path)
    names: list[str] = []
    for group in document["groups"]:
        name = group["name"]
        if name not in names:
            names.append(name)
    return names


def load_circle_actions(path: Path | str | None = None) -> list[dict]:
    """Return the Create circle and Join Ajo rows from the actions file."""
    action_path = DEFAULT_ACTIONS_PATH if path is None else Path(path)
    if not action_path.is_file():
        raise FileNotFoundError(f"Circle actions file not found at {action_path}.")
    with action_path.open(encoding="utf-8") as handle:
        document = json.load(handle)
    return _validate_actions(document)


def names_for_viewer(username, role, path: Path | str | None = None) -> list[str]:
    """Group names the signed-in persona belongs to, in document order.

    Stub usernames use the same viewer mapping as My Ajo: ``admintest`` is
    the admin of both groups, and ``membertest`` is the member of one group.
    """
    from pages.my_ajo import resolve_viewer

    document = _persona_document(path)
    viewer = resolve_viewer(document, username, role)
    if not viewer:
        return []
    membership = viewer.get("groups") or []
    allowed = set(membership) if isinstance(membership, list) else set()
    names: list[str] = []
    for group in document["groups"]:
        name = group.get("name")
        if name in allowed and name not in names:
            names.append(name)
    return names


def my_circles_rows(
    persona_path: Path | str | None = None,
    actions_path: Path | str | None = None,
    username=None,
    role=None,
):
    """Dash rows for the sidebar: this person's circles, then Create circle, then Join Ajo."""
    if username is None and role is None:
        names = load_circle_names(persona_path)
    else:
        names = names_for_viewer(username, role, persona_path)
    circle_rows = [
        html.Div([html.Span(className="cdot"), name], className="circle-row")
        for name in names
    ]
    action_rows = [
        html.Div([icon(action["icon"]), action["label"]], className="circle-row muted")
        for action in load_circle_actions(actions_path)
    ]
    return circle_rows + action_rows


def _persona_document(path: Path | str | None):
    if path is not None:
        return load_personas(path)
    try:
        return load_personas()
    except FileNotFoundError:
        return load_personas(EXAMPLE_PERSONAS_PATH)


def _validate_actions(document: dict) -> list[dict]:
    if not isinstance(document, dict):
        raise ValueError("Circle actions document must be a JSON object.")
    actions = document.get("actions")
    if not isinstance(actions, list):
        raise ValueError("Circle actions document must include an 'actions' list.")
    if [action.get("id") if isinstance(action, dict) else None for action in actions] != list(ACTION_ORDER):
        raise ValueError(
            "Circle actions must be Create circle (create-circle) followed by Join Ajo (join-ajo)."
        )
    cleaned = []
    for action in actions:
        if not isinstance(action, dict):
            raise ValueError("Each circle action must be an object.")
        label = action.get("label")
        icon_name = action.get("icon")
        if not isinstance(label, str) or not label.strip():
            raise ValueError(f"Circle action {action.get('id')!r} needs a label.")
        if icon_name not in ICONS:
            raise ValueError(f"Circle action {action.get('id')!r} has an unknown icon {icon_name!r}.")
        cleaned.append({"id": action["id"], "label": label, "icon": icon_name})
    return cleaned
