"""Local-only stub sign-in for the admintest and membertest profiles.

The stub is refused unless ALLOW_LOCAL_STUB_LOGIN is explicitly enabled and the
process is bound to a loopback address in a local environment. Enabling the
flag anywhere else aborts startup. Roles are fixed in code: the client cannot
choose one, and the credentials file cannot grant a different role.
"""

from __future__ import annotations

import hmac
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

FLAG_NAME = "ALLOW_LOCAL_STUB_LOGIN"
DEFAULT_STUB_USERS_FILE = "local/stub-users.json"
LOCAL_BIND_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
LOCAL_ENV_NAMES = frozenset({"", "local"})
TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
STUB_ROLES = {"admintest": "admin", "membertest": "member"}
PLACEHOLDER_PASSWORDS = frozenset(
    {
        "",
        "replace-me",
        "changeme",
        "password",
        "your-password",
    }
)
ADMIN_ONLY_PAGES = frozenset({"payouts"})
APP_PAGES = frozenset(
    {
        "home",
        "members",
        "payouts",
        "credit",
        "autoloan",
        "wallet",
        "circle",
        "settings",
        "dd-overview",
        "getstarted-2",
        "getstarted-3",
        "getstarted-uk-loading",
        "getstarted-4",
    }
)
AUTH_PAGES = frozenset(
    {
        "landing",
        "signin",
        "getstarted-1",
    }
)
SIGNIN_FAILED = "Sign-in failed."


class StubCredentialsError(Exception):
    def __init__(self, messages: list[str]):
        super().__init__(messages[0] if messages else "stub credentials error")
        self.messages = messages


@dataclass(frozen=True)
class StubIdentity:
    username: str
    role: str


def _source(source: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if source is None else source


def _raw(source: Mapping[str, str], name: str) -> str:
    value = source.get(name)
    if value is None:
        return ""
    return str(value).strip()


def flag_enabled(source: Mapping[str, str] | None = None) -> bool:
    return _raw(_source(source), FLAG_NAME).lower() in TRUE_VALUES


def bind_host(source: Mapping[str, str] | None = None) -> str:
    """Return the configured bind host. An unset host is not treated as local."""
    return _raw(_source(source), "DASH_HOST").lower()


def app_env(source: Mapping[str, str] | None = None) -> str:
    return _raw(_source(source), "AJO_ENV").lower()


def is_loopback_host(host: str) -> bool:
    return host.strip().lower() in LOCAL_BIND_HOSTS


def policy_problems(source: Mapping[str, str] | None = None) -> list[str]:
    problems = []
    host = bind_host(source)
    if not is_loopback_host(host):
        shown = host or "(unset)"
        problems.append(
            f"DASH_HOST is {shown}; stub sign-in requires an explicit bind of "
            "127.0.0.1, localhost, or ::1."
        )
    env_name = app_env(source)
    if env_name not in LOCAL_ENV_NAMES:
        problems.append(
            f"AJO_ENV is {env_name!r}; stub sign-in requires AJO_ENV to be unset or 'local'."
        )
    return problems


def stub_login_allowed(source: Mapping[str, str] | None = None) -> bool:
    return flag_enabled(source) and not policy_problems(source)


def credentials_path(source: Mapping[str, str] | None = None) -> Path:
    raw = _raw(_source(source), "STUB_USERS_FILE") or DEFAULT_STUB_USERS_FILE
    return Path(raw)


def _is_example_file(path: Path) -> bool:
    name = path.name.lower()
    return ".example" in name


def _fail(messages: list[str]) -> None:
    for line in messages:
        print(f"ERROR: {line}", file=sys.stderr)
    raise SystemExit(1)


def _credentials_error(messages: list[str]) -> None:
    raise StubCredentialsError(messages)


def load_stub_passwords(path: Path) -> dict[str, str]:
    if _is_example_file(path):
        _credentials_error(
            [
                f"Refusing to load stub passwords from the example file: {path}",
                "Copy local/stub-users.example.json to local/stub-users.json and set local passwords.",
                "Do not commit that file.",
            ]
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        _credentials_error(
            [
                f"Stub credentials file not found: {path}",
                "Copy local/stub-users.example.json to local/stub-users.json and set local passwords.",
                "Do not commit that file.",
            ]
        )
    except json.JSONDecodeError as exc:
        _credentials_error([f"Stub credentials file is not valid JSON: {path} ({exc})."])
    if not isinstance(data, dict):
        _credentials_error([f"Stub credentials file must be a JSON object: {path}"])

    passwords: dict[str, str] = {}
    for username in STUB_ROLES:
        value = data.get(username)
        if value is None:
            passwords[username] = ""
        elif not isinstance(value, str):
            _credentials_error([f"Password for {username} must be a string in {path}."])
        else:
            passwords[username] = value
    return passwords


def _placeholder_problems(passwords: Mapping[str, str]) -> list[str]:
    problems = []
    for username in STUB_ROLES:
        password = passwords.get(username, "")
        if password.strip().lower() in PLACEHOLDER_PASSWORDS:
            problems.append(
                f"Password for {username} is missing or still a placeholder. "
                "Set a local password in the git-ignored credentials file."
            )
    return problems


def enforce_local_stub_policy(source: Mapping[str, str] | None = None) -> None:
    """Abort when the stub flag is on outside a local-only setup.

    A disabled flag does not require credentials and does not stop startup.
    """
    if not flag_enabled(source):
        return
    problems = policy_problems(source)
    if problems:
        _fail(
            [
                "ALLOW_LOCAL_STUB_LOGIN is enabled, but this is not a local-only environment.",
                "Stub sign-in (admintest / membertest) must never run outside localhost.",
                "Refusing to start.",
                *problems,
            ]
        )
    path = credentials_path(source)
    try:
        passwords = load_stub_passwords(path)
    except StubCredentialsError as exc:
        _fail(exc.messages)
    placeholder_problems = _placeholder_problems(passwords)
    if placeholder_problems:
        _fail(
            [
                "ALLOW_LOCAL_STUB_LOGIN is enabled, but stub credentials are not set.",
                *placeholder_problems,
                "Refusing to start.",
            ]
        )


def authenticate(
    username: object,
    password: object,
    source: Mapping[str, str] | None = None,
) -> StubIdentity | None:
    """Return the fixed stub identity, or None when sign-in must be refused.

    A disabled flag, a non-local bind, a non-local environment, a missing
    credentials file, or a bad password all refuse sign-in. This never raises
    for those cases and never reads a role from the caller.
    """
    if not isinstance(username, str) or not isinstance(password, str):
        return None
    username = username.strip()
    if len(username) > 64 or len(password) > 256:
        return None
    if username not in STUB_ROLES or not stub_login_allowed(source):
        hmac.compare_digest(b"invalid", b"invalid")
        return None

    path = credentials_path(source)
    try:
        passwords = load_stub_passwords(path)
    except StubCredentialsError:
        return None
    stored = passwords.get(username, "")
    if stored.strip().lower() in PLACEHOLDER_PASSWORDS:
        return None
    matched = hmac.compare_digest(stored.encode("utf-8"), password.encode("utf-8"))
    if not matched:
        return None
    return StubIdentity(username=username, role=STUB_ROLES[username])


def gate_page(page: str | None, role: str | None) -> str:
    """Choose the page the server will render. Role must come from the server."""
    if page not in APP_PAGES and page not in AUTH_PAGES:
        page = "landing"
    if role not in {"admin", "member"}:
        if page in APP_PAGES:
            return "signin"
        return page or "landing"
    if page in ADMIN_ONLY_PAGES and role != "admin":
        return "home"
    return page or "landing"


def nav_entries(nav: list, role: str | None) -> list:
    if role != "admin":
        return [item for item in nav if item[0] not in ADMIN_ONLY_PAGES]
    return list(nav)
