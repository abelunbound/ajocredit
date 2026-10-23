"""Dev-only email inbox.

Messages go to an in-memory list and, outside the test suite, to a
git-ignored folder under ``local/email-inbox``. The body is the inbox copy
of the message. It is never written to the application log.

The dev sender is allowed only when ``AJO_ENV`` is ``local`` or ``dev``.
Setting ``EMAIL_SENDER=dev`` anywhere else, including when ``AJO_ENV`` is
unset, refuses to start. With no real provider configured, send raises
``EmailNotConfigured`` and the email endpoints fail closed.
"""

from __future__ import annotations

import json
import os
import secrets
import sys
from typing import Mapping

from backend.clock import now as clock_now

FLAG_VALUES = frozenset({"dev", "file", "inbox", "console"})
DEV_ENVS = frozenset({"local", "dev"})
# Cwd-relative, not package-relative. The launcher cds to the repo root first.
# .gitignore ignores local/email-inbox/.
DEFAULT_INBOX = "local/email-inbox"

_memory: list[dict[str, str]] = []


class EmailNotConfigured(RuntimeError):
    """No allowed sender is configured for this process."""


def _source(source: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if source is None else source


def _raw(source: Mapping[str, str], name: str) -> str:
    value = source.get(name)
    if value is None:
        return ""
    return str(value).strip()


def app_env(source: Mapping[str, str] | None = None) -> str:
    return _raw(_source(source), "AJO_ENV").lower()


def dev_email_allowed(source: Mapping[str, str] | None = None) -> bool:
    """True only for a local or dev process. Unset ``AJO_ENV`` is not allowed."""
    return app_env(source) in DEV_ENVS


def _explicit_dev_sender(source: Mapping[str, str] | None = None) -> bool:
    return _raw(_source(source), "EMAIL_SENDER").lower() in FLAG_VALUES


def policy_problems(source: Mapping[str, str] | None = None) -> list[str]:
    """Reasons startup must stop because the dev sender was turned on illegally."""
    if not _explicit_dev_sender(source):
        return []
    if dev_email_allowed(source):
        return []
    env_name = app_env(source) or "(unset)"
    return [
        f"AJO_ENV is {env_name!r}; the dev email sender is only allowed when "
        "AJO_ENV is local or dev.",
        "Refusing to start. Configure a real email provider before sending mail.",
    ]


def enforce_dev_email_policy(source: Mapping[str, str] | None = None) -> None:
    """Abort when EMAIL_SENDER selects the dev inbox outside local or dev."""
    problems = policy_problems(source)
    if not problems:
        return
    for line in problems:
        print(f"ERROR: {line}", file=sys.stderr)
    raise SystemExit(1)


def sender_available(source: Mapping[str, str] | None = None) -> bool:
    """Whether this process may send through the dev inbox."""
    if policy_problems(source):
        return False
    if not dev_email_allowed(source):
        return False
    selected = _raw(_source(source), "EMAIL_SENDER").lower()
    return selected in FLAG_VALUES or selected == ""


def memory_inbox() -> list[dict[str, str]]:
    """Copies of messages accepted by the dev sender. Tests read this."""
    return [dict(item) for item in _memory]


def clear_memory_inbox() -> None:
    _memory.clear()


def _inbox_dir(source: Mapping[str, str]) -> str | None:
    """Folder for the dev inbox. Tests stay in memory unless a path is set."""
    configured = _raw(source, "AJO_EMAIL_INBOX")
    if configured:
        return configured
    if _raw(source, "PYTEST_CURRENT_TEST"):
        return None
    return DEFAULT_INBOX


def send_message(*, recipient: str, subject: str, body: str, source: Mapping[str, str] | None = None) -> None:
    """Deliver one message to the dev inbox. Never logs the body or recipient."""
    current = _source(source)
    if not sender_available(current):
        raise EmailNotConfigured(
            "No email provider is configured. The dev inbox is only available "
            "when AJO_ENV is local or dev."
        )
    record = {
        "to": recipient,
        "subject": subject,
        "body": body,
        "created_at": clock_now().isoformat(),
    }
    _memory.append(record)
    folder = _inbox_dir(current)
    if folder is None:
        return
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{secrets.token_hex(8)}.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(record, handle)
