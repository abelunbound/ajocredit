"""Seeded test circles. Identities are obviously fake and carry no bank details.

The committed file is ``data/seeded_circles.json``. It is synthetic fixture
data for tests. It is not a ledger and it is not loaded in production.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# This file lives in tests/fixtures/. The seed JSON stays at the repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
SEEDED_CIRCLES_PATH = REPO_ROOT / "data" / "seeded_circles.json"

FAKE_NAME_MARKERS = (
    "test",
    "fake",
    "dummy",
    "example",
    "sample",
    "placeholder",
    "mock",
    "sandbox",
    "demo",
    "notaperson",
    "fictional",
    "synthetic",
)
DUMMY_EMAIL_SUFFIXES = (
    "@example.test",
    "@example.com",
    "@example.org",
    "@example.invalid",
)
FORBIDDEN_KEYS = frozenset(
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
        "account_no",
        "iban",
        "bic",
        "swift",
        "bank",
        "bank_name",
        "bank_details",
        "bank_account",
        "card_number",
        "pan",
        "cvv",
        "routing_number",
        "bsb",
        "ifsc",
        "clabe",
        "ni_number",
        "date_of_birth",
        "password",
        "hashed_password",
    }
)

# UK sort codes look like 20-00-00. A bare 8-digit string looks like an account
# number, and 13–19 digits look like a card. IBAN is two letters, two digits,
# then the body.
_SORT_CODE = re.compile(r"\d{2}-\d{2}-\d{2}")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
_ACCOUNT = re.compile(r"\d{8}")
_CARD = re.compile(r"\d{13,19}")


def member_is_preverified(member: dict) -> bool:
    """Seeded test users are verified unless the seed sets ``email_verified`` false.

    Missing the field means pre-verified, so existing fixtures can sign in and
    join without a mail provider. An explicit false leaves the account unverified.
    """
    if "email_verified" not in member:
        return True
    value = member["email_verified"]
    if not isinstance(value, bool):
        raise ValueError("Seeded member email_verified must be true or false.")
    return value


def seeded_verified_at(member: dict, when):
    """Timestamp to store for a seeded member, or None when they must verify."""
    if member_is_preverified(member):
        return when
    return None


def load_seeded_circles(path: Path | str | None = None) -> dict:
    """Load and check the seeded-circle document."""
    seed_path = SEEDED_CIRCLES_PATH if path is None else Path(path)
    if not seed_path.is_file():
        raise FileNotFoundError(f"Seeded circles file not found at {seed_path}.")
    with seed_path.open(encoding="utf-8") as handle:
        document = json.load(handle)
    validate_seeded_circles(document)
    return document


def validate_seeded_circles(document: dict) -> None:
    """Raise ``ValueError`` when a seed looks like a real person or a bank account."""
    if not isinstance(document, dict):
        raise ValueError("Seeded circles document must be a JSON object.")
    circles = document.get("circles")
    if not isinstance(circles, list) or not circles:
        raise ValueError("Seeded circles document must include a non-empty 'circles' list.")

    _reject_forbidden_keys(document)
    _reject_bank_like_strings(document)

    seen_circle_ids: set[str] = set()
    for circle in circles:
        if not isinstance(circle, dict):
            raise ValueError("Each seeded circle must be an object.")
        circle_id = circle.get("id")
        name = circle.get("name")
        members = circle.get("members")
        if not isinstance(circle_id, str) or not circle_id:
            raise ValueError("Each seeded circle needs a non-empty id.")
        if circle_id in seen_circle_ids:
            raise ValueError(f"Duplicate seeded circle id {circle_id!r}.")
        seen_circle_ids.add(circle_id)
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Seeded circle {circle_id} needs a name.")
        if not isinstance(members, list) or not members:
            raise ValueError(f"Seeded circle {circle_id} needs at least one member.")

        contribution = circle.get("contribution_pence")
        if not isinstance(contribution, int) or isinstance(contribution, bool) or contribution < 0:
            raise ValueError(
                f"Seeded circle {circle_id} contribution_pence must be a non-negative integer."
            )

        seen_members: set[str] = set()
        admins = 0
        for member in members:
            if not isinstance(member, dict):
                raise ValueError(f"Seeded circle {circle_id} has a member that is not an object.")
            _require_fake_member(circle_id, member)
            member_is_preverified(member)
            member_id = member["id"]
            if member_id in seen_members:
                raise ValueError(f"Seeded circle {circle_id} repeats member {member_id!r}.")
            seen_members.add(member_id)
            if member["role"] == "admin":
                admins += 1
        if admins != 1:
            raise ValueError(f"Seeded circle {circle_id} must have exactly one admin.")


def _require_fake_member(circle_id: str, member: dict) -> None:
    member_id = member.get("id")
    name = member.get("name")
    email = member.get("email")
    role = member.get("role")
    if not isinstance(member_id, str) or not member_id:
        raise ValueError(f"Seeded circle {circle_id} has a member without an id.")
    if not isinstance(name, str) or not _obviously_fake_name(name):
        raise ValueError(
            f"Seeded circle {circle_id} member {member_id!r} must use an obviously "
            "fake name (for example Testperson, Sampledata, or Faketest)."
        )
    if not isinstance(email, str) or not email.endswith(DUMMY_EMAIL_SUFFIXES):
        raise ValueError(
            f"Seeded circle {circle_id} member {member_id!r} email must use an "
            "example domain such as @example.test."
        )
    if role not in ("admin", "member"):
        raise ValueError(f"Seeded circle {circle_id} member {member_id!r} role is invalid.")


def _obviously_fake_name(name: str) -> bool:
    lowered = name.casefold()
    return any(marker in lowered for marker in FAKE_NAME_MARKERS)


def _reject_forbidden_keys(value: object, where: str = "seed") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).casefold() in FORBIDDEN_KEYS:
                raise ValueError(
                    f"Seeded circles must not include personal or bank fields: {key!r}."
                )
            _reject_forbidden_keys(child, f"{where}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_forbidden_keys(child, f"{where}[{index}]")


def _reject_bank_like_strings(value: object) -> None:
    if isinstance(value, dict):
        for child in value.values():
            _reject_bank_like_strings(child)
        return
    if isinstance(value, list):
        for child in value:
            _reject_bank_like_strings(child)
        return
    if not isinstance(value, str):
        return
    if _SORT_CODE.search(value):
        raise ValueError(f"Seeded circles must not contain a sort code: {value!r}.")
    if _IBAN.search(value):
        raise ValueError(f"Seeded circles must not contain an IBAN: {value!r}.")
    digits = re.sub(r"[\s-]", "", value)
    if _ACCOUNT.fullmatch(digits) or _CARD.fullmatch(digits):
        raise ValueError(f"Seeded circles must not contain a card or account number: {value!r}.")
