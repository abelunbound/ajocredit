"""Interactive API docs are on only when AJO_ENV is local or dev.

Run with: pytest tests/test_openapi_docs.py -v
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ["JWT_SECRET_KEY"] = "test-only-jwt-secret-key-32chars!!"
os.environ["ALLOW_LOCAL_STUB_LOGIN"] = "false"
os.environ["SEED_DEMO_ACCOUNTS"] = "false"

_configured_url = os.environ.get("DATABASE_URL", "")
if not _configured_url.startswith("postgres"):
    _db_dir = tempfile.mkdtemp(prefix="ajo-openapi-")
    os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_db_dir) / "ajo.db")

import backend.api as api
import pytest
from fastapi.testclient import TestClient

DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


def _client_for_env(monkeypatch, env: str | None) -> TestClient:
    if env is None:
        monkeypatch.delenv("AJO_ENV", raising=False)
    else:
        monkeypatch.setenv("AJO_ENV", env)
    return TestClient(api.create_app())


@pytest.mark.parametrize("env", ["local", "dev", " Local ", "DEV"])
def test_openapi_docs_are_served_for_local_and_dev(monkeypatch, env):
    client = _client_for_env(monkeypatch, env)
    for path in DOCS_PATHS:
        response = client.get(path)
        assert response.status_code == 200, path


@pytest.mark.parametrize("env", ["prod", "staging"])
def test_openapi_docs_are_hidden_for_prod_and_staging(monkeypatch, env):
    client = _client_for_env(monkeypatch, env)
    for path in DOCS_PATHS:
        assert client.get(path).status_code == 404


def test_openapi_docs_are_hidden_when_ajo_env_is_unset(monkeypatch):
    client = _client_for_env(monkeypatch, None)
    for path in DOCS_PATHS:
        assert client.get(path).status_code == 404
