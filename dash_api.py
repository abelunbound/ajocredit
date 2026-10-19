"""Server-side calls from Dash to the FastAPI app.

Tokens stay in this process. The browser session cookie holds an opaque id
only. Tokens are not written to logs, URLs, or the browser's localStorage.

Sign-in on a laptop accepts only ``admintest`` and ``membertest``. Their
roles are read back from the API. This module does not choose a role.
"""

from __future__ import annotations

import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable

LOCAL_ACCOUNTS = {
    "admintest": "admintest@example.test",
    "membertest": "membertest@example.test",
}
_EMAIL_TO_USERNAME = {email: username for username, email in LOCAL_ACCOUNTS.items()}
_DEV_ENVS = frozenset({"local", "dev"})

# Tests replace HTTP with an in-process sender. Production uses urllib.
Send = Callable[..., tuple[int, object]]
_transport_send: Send | None = None


class TokenVault:
    """Process-local access and refresh tokens, keyed by an opaque id."""

    def __init__(self) -> None:
        self._rows: dict[str, dict[str, str]] = {}

    def put(self, access_token: str, refresh_token: str) -> str:
        sid = secrets.token_urlsafe(32)
        self._rows[sid] = {"access_token": access_token, "refresh_token": refresh_token}
        return sid

    def get(self, sid: str | None) -> dict[str, str] | None:
        if not sid:
            return None
        return self._rows.get(sid)

    def update(self, sid: str, access_token: str, refresh_token: str) -> None:
        self._rows[sid] = {"access_token": access_token, "refresh_token": refresh_token}

    def drop(self, sid: str | None) -> None:
        if sid:
            self._rows.pop(sid, None)

    def __repr__(self) -> str:
        return f"TokenVault(sessions={len(self._rows)})"


VAULT = TokenVault()


@dataclass(frozen=True)
class ApiIdentity:
    username: str
    role: str | None
    sid: str
    user_id: int | None
    email_verified: bool
    circles: list


def api_base() -> str:
    return os.environ.get("AJO_API_BASE", "").strip().rstrip("/")


def api_mode() -> bool:
    """True when Dash should call the API instead of the local stub."""
    return bool(api_base())


def install_transport_for_tests(send: Send | None) -> None:
    """Use an in-process sender. ``None`` restores urllib."""
    global _transport_send
    _transport_send = send


def local_username(value: object) -> str | None:
    """Map a sign-in field to admintest or membertest. Anyone else is refused."""
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if cleaned in LOCAL_ACCOUNTS:
        return cleaned
    lowered = cleaned.lower()
    return _EMAIL_TO_USERNAME.get(lowered)


def _dev_environment() -> bool:
    return os.environ.get("AJO_ENV", "").strip().lower() in _DEV_ENVS


def _decode_body(raw: bytes) -> object:
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


class ApiUnavailable(Exception):
    """The API could not be reached, timed out, or returned a server error."""


SERVICE_UNAVAILABLE = "Service unavailable, please try again shortly"


def _unavailable(status: int) -> bool:
    """Connection failures, timeouts, and server errors. Not a refused login."""
    return status == 0 or status == 408 or status >= 500


def _urllib_send(method: str, path: str, body: dict | None, headers: dict, params: dict | None) -> tuple[int, object]:
    base = api_base()
    if not base:
        raise RuntimeError("AJO_API_BASE is not set.")
    query = ""
    if params:
        pairs = []
        for key, value in params.items():
            if value is None:
                continue
            pairs.append(
                urllib.parse.quote(str(key), safe="")
                + "="
                + urllib.parse.quote(str(value), safe="")
            )
        if pairs:
            query = "?" + "&".join(pairs)
    url = base + path + query
    data = None
    hdrs = dict(headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs["Content-Type"] = "application/json"
        hdrs["Accept"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, _decode_body(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, _decode_body(exc.read())
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
        return 0, None


def _send(method: str, path: str, body: dict | None, headers: dict, params: dict | None) -> tuple[int, object]:
    try:
        if _transport_send is not None:
            return _transport_send(method, path, body, headers, params)
        return _urllib_send(method, path, body, headers, params)
    except (TimeoutError, ConnectionError):
        return 0, None


def safe_detail(payload: object, fallback: str) -> str:
    """A short API message. Tokens and long bodies are not shown."""
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str):
            text = detail.strip()
            lowered = text.lower()
            if text and len(text) <= 180 and "token" not in lowered and "bearer" not in lowered:
                return text
    return fallback


def _refresh(sid: str) -> bool:
    row = VAULT.get(sid)
    if row is None:
        return False
    status, payload = _send(
        "POST",
        "/api/v1/auth/refresh",
        {"refresh_token": row["refresh_token"]},
        {},
        None,
    )
    if _unavailable(status):
        return False
    if status != 200 or not isinstance(payload, dict):
        VAULT.drop(sid)
        return False
    access = payload.get("access_token")
    refresh = payload.get("refresh_token")
    if not isinstance(access, str) or not isinstance(refresh, str) or not access or not refresh:
        VAULT.drop(sid)
        return False
    VAULT.update(sid, access, refresh)
    return True


def request(
    method: str,
    path: str,
    *,
    json_body: dict | None = None,
    params: dict | None = None,
    sid: str | None = None,
    refresh_on_unauthorized: bool = True,
) -> tuple[int, object]:
    """Call the API. A 401 retries once with a rotated refresh token."""
    headers: dict[str, str] = {}
    row = VAULT.get(sid)
    if row is not None:
        headers["Authorization"] = f"Bearer {row['access_token']}"
    status, payload = _send(method, path, json_body, headers, params)
    if status == 401 and refresh_on_unauthorized and row is not None and path != "/api/v1/auth/refresh":
        if not _refresh(sid or ""):
            return status, payload
        refreshed = VAULT.get(sid)
        if refreshed is None:
            return status, payload
        headers = {"Authorization": f"Bearer {refreshed['access_token']}"}
        status, payload = _send(method, path, json_body, headers, params)
    return status, payload


def _role_from_circles(circles: list[dict]) -> str | None:
    roles = set()
    for circle in circles:
        role = circle.get("role")
        if role in {"admin", "member"}:
            roles.add(role)
    if "admin" in roles:
        return "admin"
    if "member" in roles:
        return "member"
    return None


def _confirmed_circles(sid: str, listed: list) -> list[dict]:
    """Re-read each circle so the role is the one the server stores."""
    confirmed: list[dict] = []
    for item in listed:
        if not isinstance(item, dict):
            continue
        circle_id = item.get("circle_id")
        name = item.get("name")
        if not isinstance(circle_id, int) or not isinstance(name, str) or not name:
            continue
        status, payload = request("GET", f"/api/v1/circles/{circle_id}", sid=sid)
        if _unavailable(status):
            raise ApiUnavailable()
        role = None
        if status == 200 and isinstance(payload, dict) and payload.get("role") in {"admin", "member"}:
            role = payload["role"]
            if isinstance(payload.get("name"), str) and payload["name"]:
                name = payload["name"]
        if role is None:
            continue
        confirmed.append({"circle_id": circle_id, "name": name, "role": role})
    return confirmed


def load_circles(sid: str) -> list[dict]:
    status, payload = request("GET", "/api/v1/circles", sid=sid)
    if _unavailable(status):
        raise ApiUnavailable()
    if status != 200 or not isinstance(payload, dict):
        return []
    listed = payload.get("circles")
    if not isinstance(listed, list):
        return []
    return _confirmed_circles(sid, listed)


def sign_in(username: object, password: object) -> ApiIdentity | None:
    """Sign in through the API. Returns None when the API refuses."""
    if not isinstance(password, str) or not password:
        return None
    handle = local_username(username)
    if handle is None or not _dev_environment():
        return None
    status, payload = _send(
        "POST",
        "/api/v1/auth/login",
        {"email": LOCAL_ACCOUNTS[handle], "password": password},
        {},
        None,
    )
    if _unavailable(status):
        raise ApiUnavailable()
    if status != 200 or not isinstance(payload, dict):
        return None
    access = payload.get("access_token")
    refresh = payload.get("refresh_token")
    if not isinstance(access, str) or not isinstance(refresh, str) or not access or not refresh:
        return None
    sid = VAULT.put(access, refresh)
    try:
        me_status, me = request("GET", "/api/v1/me", sid=sid)
        if _unavailable(me_status):
            raise ApiUnavailable()
        if me_status != 200 or not isinstance(me, dict):
            VAULT.drop(sid)
            return None
        circles = load_circles(sid)
        role = _role_from_circles(circles)
        user_id = me.get("user_id") if isinstance(me.get("user_id"), int) else None
        return ApiIdentity(
            username=handle,
            role=role,
            sid=sid,
            user_id=user_id,
            email_verified=bool(me.get("email_verified")),
            circles=circles,
        )
    except ApiUnavailable:
        VAULT.drop(sid)
        raise


def logout(sid: str | None) -> None:
    if not sid or VAULT.get(sid) is None:
        VAULT.drop(sid)
        return
    request("POST", "/api/v1/auth/logout", sid=sid)
    VAULT.drop(sid)


def signup(name: str, email: str, password: str) -> tuple[int, object]:
    """Create an account. Only synthetic @example.test addresses are sent."""
    address = email.strip().lower()
    if not address.endswith("@example.test"):
        return 422, {"detail": "Use an @example.test address."}
    return _send(
        "POST",
        "/api/v1/auth/signup",
        {"name": name.strip(), "email": address, "password": password},
        {},
        None,
    )


def sync_session_force() -> None:
    """Read circle roles again after a create or join in this same request."""
    try:
        from flask import g, has_request_context
    except ImportError:
        return
    if has_request_context():
        g.ajo_api_synced = False
    sync_session()


def sync_session() -> None:
    """Refresh circle roles from the API once per browser request.

    The stored role is replaced by the server's answer. A query string is ignored.
    """
    if not api_mode():
        return
    try:
        from flask import g, has_request_context, session
    except ImportError:
        return
    if not has_request_context():
        return
    if getattr(g, "ajo_api_synced", False):
        return
    g.ajo_api_synced = True
    sid = session.get("api_sid")
    if not isinstance(sid, str) or VAULT.get(sid) is None:
        return
    me_status, me = request("GET", "/api/v1/me", sid=sid)
    if _unavailable(me_status):
        return
    if me_status == 401:
        if VAULT.get(sid) is None:
            logout(sid)
            session.clear()
        return
    if me_status == 200 and isinstance(me, dict):
        session["email_verified"] = bool(me.get("email_verified"))
        if isinstance(me.get("user_id"), int):
            session["user_id"] = me["user_id"]
    try:
        circles = load_circles(sid)
    except ApiUnavailable:
        return
    session["circles"] = circles
    session["role"] = _role_from_circles(circles)


def confirm_payouts() -> None:
    """Ask the server which circles allow payouts. A 403 drops that circle to member."""
    if not api_mode():
        return
    try:
        from flask import has_request_context, session
    except ImportError:
        return
    if not has_request_context():
        return
    sid = session.get("api_sid")
    if not isinstance(sid, str) or VAULT.get(sid) is None:
        return
    updated = []
    for circle in session.get("circles") or []:
        if not isinstance(circle, dict):
            continue
        if circle.get("role") != "admin" or not isinstance(circle.get("circle_id"), int):
            updated.append(circle)
            continue
        status, payload = request(
            "GET",
            f"/api/v1/circles/{circle['circle_id']}/payouts",
            sid=sid,
        )
        if _unavailable(status):
            return
        if status == 200 and isinstance(payload, dict) and payload.get("role") == "admin":
            updated.append({**circle, "role": "admin"})
            continue
        if status == 403:
            updated.append({**circle, "role": "member"})
            continue
        updated.append(circle)
    session["circles"] = updated
    roles = {item.get("role") for item in updated}
    if "admin" in roles:
        session["role"] = "admin"
    elif "member" in roles:
        session["role"] = "member"
    else:
        session["role"] = None


def remember_identity(identity: ApiIdentity) -> None:
    """Copy the API identity into the Flask session. Tokens stay in the vault."""
    from flask import session

    session["username"] = identity.username
    session["role"] = identity.role
    session["api_sid"] = identity.sid
    session["circles"] = identity.circles
    session["email_verified"] = identity.email_verified
    if identity.user_id is not None:
        session["user_id"] = identity.user_id
