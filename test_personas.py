"""Tests for the synthetic persona fixture and its loader."""

import json
import subprocess
from pathlib import Path

import pytest

from pages.personas import (
    DEFAULT_PERSONAS_PATH,
    EXAMPLE_PERSONAS_PATH,
    load_personas,
    validate_personas,
)

REPO_ROOT = Path(__file__).resolve().parent


def test_loader_reads_example_personas():
    """The committed template loads and matches the M1 persona rules."""
    document = load_personas(EXAMPLE_PERSONAS_PATH)

    assert len(document["personas"]) == 10
    assert {group["name"] for group in document["groups"]} == {
        "Brum Builders",
        "Sister Circle Ajo",
    }

    both = [
        persona
        for persona in document["personas"]
        if set(persona["groups"]) == {"Brum Builders", "Sister Circle Ajo"}
    ]
    single = [persona for persona in document["personas"] if len(persona["groups"]) == 1]
    admins = [persona for persona in document["personas"] if persona["role"] == "admin"]

    assert len(both) == 5
    assert len(single) == 5
    assert len(admins) == 1
    assert admins[0]["id"] == "persona-01"
    assert {group["created_by"] for group in document["groups"]} == {"persona-01"}

    for persona in document["personas"]:
        assert persona["name"].strip()
        assert persona["email"].endswith("@example.test")
        assert persona["password"]


def test_local_personas_file_is_gitignored():
    """The live personas file is ignored, and the example template is tracked."""
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "data/personas.json"],
        cwd=REPO_ROOT,
        check=False,
    )
    assert ignored.returncode == 0

    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "data/personas.json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert tracked.returncode != 0

    example = subprocess.run(
        ["git", "check-ignore", "-q", "data/personas.example.json"],
        cwd=REPO_ROOT,
        check=False,
    )
    assert example.returncode != 0
    assert EXAMPLE_PERSONAS_PATH.is_file()
    assert DEFAULT_PERSONAS_PATH.name == "personas.json"


def test_loader_uses_gitignored_path_by_default(tmp_path, monkeypatch):
    """The default path is the git-ignored file, not the committed example."""
    local_file = tmp_path / "personas.json"
    local_file.write_text(EXAMPLE_PERSONAS_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr("pages.personas.DEFAULT_PERSONAS_PATH", local_file)

    document = load_personas()
    assert len(document["personas"]) == 10


def test_missing_personas_file_explains_the_copy_step(tmp_path, monkeypatch):
    missing = tmp_path / "personas.json"
    monkeypatch.setattr("pages.personas.DEFAULT_PERSONAS_PATH", missing)

    with pytest.raises(FileNotFoundError, match="Copy"):
        load_personas()


def test_loader_rejects_real_personal_data():
    document = json.loads(EXAMPLE_PERSONAS_PATH.read_text(encoding="utf-8"))
    document["personas"][0]["phone"] = "07000000000"

    with pytest.raises(ValueError, match="personal or bank"):
        validate_personas(document)
