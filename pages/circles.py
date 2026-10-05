"""Dummy Ajo circles built from the synthetic persona file.

Each circle records the persona who created it. That creator is the admin
of that Ajo. The live personas file is git-ignored; when it is missing, the
committed example is used so the UI still shows fake local data. Passwords
and emails are not copied onto a circle.
"""

from __future__ import annotations

from pathlib import Path

from pages.personas import (
    DEFAULT_PERSONAS_PATH,
    EXAMPLE_PERSONAS_PATH,
    load_personas,
    validate_personas,
)


def circle_records(document: dict) -> list[dict]:
    """Return public circle records. The creator is the admin of each Ajo."""
    validate_personas(document)
    by_id = {persona["id"]: persona for persona in document["personas"]}
    records = []
    for group in document["groups"]:
        creator_id = group["created_by"]
        creator = by_id[creator_id]
        members = []
        for persona in document["personas"]:
            if group["name"] not in persona["groups"]:
                continue
            members.append(
                {
                    "id": persona["id"],
                    "name": persona["name"],
                    "role_in_ajo": "admin" if persona["id"] == creator_id else "member",
                }
            )
        records.append(
            {
                "name": group["name"],
                "created_by": creator_id,
                "creator_name": creator["name"],
                "admin_id": creator_id,
                "admin_name": creator["name"],
                "members": members,
            }
        )
    return records


def load_dummy_circles(path: Path | str | None = None) -> list[dict]:
    """Load dummy circles from a personas file.

    ``path`` defaults to the git-ignored local file when it exists, and to
    ``data/personas.example.json`` otherwise.
    """
    if path is None:
        source = DEFAULT_PERSONAS_PATH if DEFAULT_PERSONAS_PATH.is_file() else EXAMPLE_PERSONAS_PATH
    else:
        source = Path(path)
    return circle_records(load_personas(source))
