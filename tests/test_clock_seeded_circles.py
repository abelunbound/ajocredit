"""Seeded test circles (#36) use obviously fake identities and no bank details."""

from __future__ import annotations

import copy

import pytest

from tests.fixtures.seeded_circles import (
    SEEDED_CIRCLES_PATH,
    load_seeded_circles,
    validate_seeded_circles,
)

FAKE_MARKERS = (
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
)


def test_committed_seed_is_obviously_fake_and_has_no_bank_details():
    document = load_seeded_circles()
    assert SEEDED_CIRCLES_PATH.name == "seeded_circles.json"
    circles = document["circles"]
    assert [circle["name"] for circle in circles] == ["Brum Builders", "Sister Circle Ajo"]

    keys: list[str] = []

    def _collect(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                keys.append(str(key).casefold())
                _collect(child)
        elif isinstance(value, list):
            for child in value:
                _collect(child)

    _collect(document)
    for forbidden in ("sort_code", "account_number", "iban", "bank_details", "password"):
        assert forbidden not in keys

    for circle in circles:
        assert isinstance(circle["contribution_pence"], int)
        admins = [member for member in circle["members"] if member["role"] == "admin"]
        assert [member["name"] for member in admins] == ["Amina Testperson"]
        for member in circle["members"]:
            assert any(marker in member["name"].casefold() for marker in FAKE_MARKERS)
            assert member["email"].endswith("@example.test")
            assert set(member) == {"id", "name", "email", "role"}


def _with_member_change(**changes):
    document = load_seeded_circles()
    member = document["circles"][0]["members"][1]
    member.update(changes)
    return document


def test_seed_rejects_a_real_looking_identity():
    document = _with_member_change(name="Amaka Okonkwo", email="amaka.okonkwo@gmail.com")
    with pytest.raises(ValueError, match="obviously fake"):
        validate_seeded_circles(document)


def test_seed_rejects_a_real_mailbox_even_with_a_fake_name():
    document = _with_member_change(email="chidi.sampledata@gmail.com")
    with pytest.raises(ValueError, match="example"):
        validate_seeded_circles(document)


@pytest.mark.parametrize(
    "extra",
    [
        {"sort_code": "00-00-00"},
        {"account_number": "00000000"},
        {"iban": "GB00FAKE00000000000000"},
        {"bank_details": {"pan": "0000000000000000"}},
    ],
)
def test_seed_rejects_bank_fields(extra):
    document = load_seeded_circles()
    document["circles"][0]["members"][0].update(extra)
    with pytest.raises(ValueError, match="personal or bank"):
        validate_seeded_circles(document)


@pytest.mark.parametrize(
    "hidden",
    [
        "paid from sort code 00-00-00",
        "GB00FAKE00000000000000",
        "00000000",
        "0000 0000 0000 0000",
    ],
)
def test_seed_rejects_bank_details_hidden_in_text(hidden):
    document = load_seeded_circles()
    document["note"] = hidden
    with pytest.raises(ValueError, match="must not contain"):
        validate_seeded_circles(document)


def test_seed_rejects_a_circle_with_no_members():
    document = load_seeded_circles()
    document["circles"][0]["members"] = []
    with pytest.raises(ValueError, match="at least one member"):
        validate_seeded_circles(document)


def test_validator_does_not_mutate_the_loaded_document():
    original = load_seeded_circles()
    snapshot = copy.deepcopy(original)
    validate_seeded_circles(original)
    assert original == snapshot
