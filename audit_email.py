"""HMAC-SHA256 hashes of email addresses for the auth audit log.

The key comes from ``AUDIT_EMAIL_HMAC_KEY``. On a local or dev process the key
may instead be created in ``local/audit-email-hmac.key``, which is git-ignored.
Any other environment, including an unset ``AJO_ENV``, refuses to hash without
the environment variable. The hash is never plain SHA-256.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from pathlib import Path
from typing import Mapping

KEY_ENV = "AUDIT_EMAIL_HMAC_KEY"
KEY_FILE_ENV = "AUDIT_EMAIL_HMAC_KEY_FILE"
DEFAULT_KEY_PATH = Path("local/audit-email-hmac.key")
DEV_ENVS = frozenset({"local", "dev"})


class AuditKeyError(RuntimeError):
    """Raised when an audit email hash would have to be computed without a key."""


def _source(source: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if source is None else source


def audit_email_key(source: Mapping[str, str] | None = None) -> bytes:
    """Return the HMAC key, creating the local file only for local or dev."""
    env = _source(source)
    configured = env.get(KEY_ENV)
    if configured is not None and str(configured).strip():
        return str(configured).strip().encode("utf-8")
    app_env = str(env.get("AJO_ENV") or "").strip().lower()
    if app_env not in DEV_ENVS:
        raise AuditKeyError(
            "AUDIT_EMAIL_HMAC_KEY is required when AJO_ENV is unset or is not local or dev."
        )
    raw_path = env.get(KEY_FILE_ENV)
    path = Path(str(raw_path)) if raw_path else DEFAULT_KEY_PATH
    if path.is_file():
        stored = path.read_text(encoding="utf-8").strip()
        if stored:
            return stored.encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    generated = secrets.token_urlsafe(32)
    path.write_text(generated + "\n", encoding="utf-8")
    path.chmod(0o600)
    return generated.encode("utf-8")


def hash_audit_email(email: str, source: Mapping[str, str] | None = None) -> str:
    """HMAC-SHA256 hex digest of a normalised email. Not plain SHA-256."""
    return hmac.new(audit_email_key(source), email.encode("utf-8"), hashlib.sha256).hexdigest()
