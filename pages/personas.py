"""Load synthetic local personas for later use by the Dash UI.

The live file (``data/personas.json``) is git-ignored. Commit only
``data/personas.example.json``. Copy the example before loading the default path:

    cp data/personas.example.json data/personas.json
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PERSONAS_PATH = REPO_ROOT / "data" / "personas.json"
EXAMPLE_PERSONAS_PATH = REPO_ROOT / "data" / "personas.example.json"

BRUM_BUILDERS = "Brum Builders"
SISTER_CIRCLE = "Sister Circle Ajo"
GROUP_NAMES = (BRUM_BUILDERS, SISTER_CIRCLE)

REQUIRED_PERSONA_FIELDS = ("id", "name", "email", "password", "role", "groups")
FORBIDDEN_FIELDS = frozenset(
    {
        "phone",
        "phone_number",
        "mobile",
        "address",
        "street",
        "postcode",
        "postal_code",
        "sort_code",
        "account_number",
        "iban",
        "bank",
        "bank_details",
        "ni_number",
        "date_of_birth",
    }
)
DUMMY_EMAIL_SUFFIX = "@example.test"


def load_personas(path: Path | str | None = None) -> dict:
    """Load and check the persona document.

    ``path`` defaults to the git-ignored local file. Pass
    ``EXAMPLE_PERSONAS_PATH`` to read the committed template.
    """
    persona_path = DEFAULT_PERSONAS_PATH if path is None else Path(path)
    if not persona_path.is_file():
        raise FileNotFoundError(
            f"Personas file not found at {persona_path}. "
            f"Copy {EXAMPLE_PERSONAS_PATH} to {DEFAULT_PERSONAS_PATH}."
        )
    with persona_path.open(encoding="utf-8") as handle:
        document = json.load(handle)
    validate_personas(document)
    return document


def validate_personas(document: dict) -> None:
    """Raise ``ValueError`` when the document does not match the M1 fixture rules."""
    if not isinstance(document, dict):
        raise ValueError("Personas document must be a JSON object.")

    groups = document.get("groups")
    personas = document.get("personas")
    if not isinstance(groups, list) or not isinstance(personas, list):
        raise ValueError("Personas document must include 'groups' and 'personas' lists.")
    if len(personas) != 10:
        raise ValueError(f"Expected 10 personas, found {len(personas)}.")

    group_names = []
    creators = set()
    for group in groups:
        if not isinstance(group, dict):
            raise ValueError("Each group must be an object.")
        name = group.get("name")
        created_by = group.get("created_by")
        if name not in GROUP_NAMES:
            raise ValueError(f"Unexpected group {name!r}.")
        if not isinstance(created_by, str) or not created_by:
            raise ValueError(f"Group {name!r} must record its creator.")
        group_names.append(name)
        creators.add(created_by)
    if sorted(group_names) != sorted(GROUP_NAMES):
        raise ValueError("Document must include Brum Builders and Sister Circle Ajo once each.")

    seen_ids = set()
    seen_emails = set()
    both_groups = 0
    one_group = 0
    admins = []

    for persona in personas:
        if not isinstance(persona, dict):
            raise ValueError("Each persona must be an object.")
        forbidden = FORBIDDEN_FIELDS.intersection(persona)
        if forbidden:
            raise ValueError(f"Persona must not include personal or bank fields: {sorted(forbidden)}.")
        missing = [field for field in REQUIRED_PERSONA_FIELDS if field not in persona]
        if missing:
            raise ValueError(f"Persona is missing fields: {missing}.")

        persona_id = persona["id"]
        name = persona["name"]
        email = persona["email"]
        password = persona["password"]
        role = persona["role"]
        membership = persona["groups"]

        if not isinstance(persona_id, str) or not persona_id:
            raise ValueError("Persona id must be a non-empty string.")
        if persona_id in seen_ids:
            raise ValueError(f"Duplicate persona id {persona_id!r}.")
        seen_ids.add(persona_id)

        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Persona {persona_id} needs a name.")
        if not isinstance(email, str) or not email.endswith(DUMMY_EMAIL_SUFFIX):
            raise ValueError(
                f"Persona {persona_id} email must be a dummy address ending in {DUMMY_EMAIL_SUFFIX}."
            )
        if email in seen_emails:
            raise ValueError(f"Duplicate email {email!r}.")
        seen_emails.add(email)
        if not isinstance(password, str) or not password or any(char.isspace() for char in password):
            raise ValueError(f"Persona {persona_id} needs a simple non-empty password.")
        if role not in ("admin", "member"):
            raise ValueError(f"Persona {persona_id} role must be 'admin' or 'member'.")
        if not isinstance(membership, list) or not membership:
            raise ValueError(f"Persona {persona_id} must belong to at least one group.")
        if any(group not in GROUP_NAMES for group in membership):
            raise ValueError(f"Persona {persona_id} has an unknown group.")
        if len(set(membership)) != len(membership):
            raise ValueError(f"Persona {persona_id} lists a group more than once.")

        if len(membership) == 2:
            both_groups += 1
        elif len(membership) == 1:
            one_group += 1
        else:
            raise ValueError(f"Persona {persona_id} must be in one or both groups.")

        if role == "admin":
            admins.append(persona_id)

    if both_groups != 5:
        raise ValueError(f"Expected 5 personas in both groups, found {both_groups}.")
    if one_group != 5:
        raise ValueError(f"Expected 5 personas in only one group, found {one_group}.")
    if len(admins) != 1:
        raise ValueError(f"Expected exactly 1 admin (the group creator), found {len(admins)}.")

    admin_id = admins[0]
    if creators != {admin_id}:
        raise ValueError("Each group must record the single admin persona as its creator.")
