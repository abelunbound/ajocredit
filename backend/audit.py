"""Append-only security audit log.

Emails are stored only as HMAC-SHA256 under ``AUDIT_EMAIL_HMAC_KEY``.
Passwords, tokens, bank details, BVN, and ethnicity values are omitted.
Each row stores the hash of the previous row. Database triggers reject
UPDATE and DELETE. The caller commits.

Auth rows in ``auth_audit_events`` are copied here on flush, including a
later lockout row. ``record_role_change`` calls ``record_event`` directly.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import uuid
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy import event, or_, text
from sqlalchemy.orm import Session

import backend.audit_email as audit_email
from backend.clock import now as clock_now
from backend.database import AuditLog, AuthAuditEvent, User, get_db

PLATFORM_ADMIN = "platform_admin"
AUDIT_UNAVAILABLE = "Audit logging is not configured."
NOT_ALLOWED = "Not allowed."
ACTION_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
HEX_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
SECRET_RE = re.compile(
    r"(?i)(bearer\s+[A-Za-z0-9._\-]+|password\s*[:=]\s*\S+|token\s*[:=]\s*\S+)"
)
SENSITIVE_PARTS = (
    "password",
    "token",
    "secret",
    "bvn",
    "ethnicity",
    "bank",
    "iban",
    "sort_code",
    "account_number",
    "card",
)
# Events named in #32. Product paths write the ones that exist today.
# ``record_event`` is the writer for the rest.
LISTED_EVENTS = (
    "sign_in_success",
    "sign_in_failure",
    "logout",
    "account_locked",
    "rate_limited",
    "password_reset_requested",
    "password_reset_completed",
    "email_verification_sent",
    "email_verified",
    "role_changed",
    "permission_changed",
    "payout_position_changed",
    "admin_action",
    "ajo_created",
    "ajo_joined",
    "ajo_left",
    "member_removed",
    "settings_changed",
    "rotation_swap",
    "contribution_paid",
    "contribution_late",
    "contribution_missed",
    "delay_cover_requested",
    "delay_cover_drawn",
    "early_payout_quoted",
    "early_payout_accepted",
    "early_payout_approved",
    "payout_sent",
    "profile_changed",
    "payout_details_changed",
    "consent_given",
    "consent_withdrawn",
    "financial_data_viewed",
    "data_export_requested",
    "data_deletion_requested",
    "audit_log_read",
    "platform_role_changed",
)
MAX_VALUE_CHARS = 4000
MAX_PAGE_SIZE = 100
JWT_ALGORITHM = "HS256"

_request_ctx: ContextVar[Request | None] = ContextVar("audit_request", default=None)


def bind_request(request: Request):
    """Remember the current HTTP request for audit fields. Middleware only."""
    return _request_ctx.set(request)


def reset_request(token) -> None:
    _request_ctx.reset(token)


def current_request() -> Request | None:
    return _request_ctx.get()


def _iso(moment: datetime) -> str:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    else:
        moment = moment.astimezone(timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _safe_email_hash(email: str | None) -> str | None:
    if not email:
        return None
    try:
        return audit_email.hash_audit_email(email.strip().lower())
    except audit_email.AuditKeyError:
        return None


def _scrub_fragment(value: str) -> str:
    def email_repl(match: re.Match[str]) -> str:
        digest = _safe_email_hash(match.group(0))
        return digest if digest else "[email]"

    cleaned = EMAIL_RE.sub(email_repl, value)
    return SECRET_RE.sub("[omitted]", cleaned)


def _sensitive_key(key: str) -> bool:
    lowered = key.lower().replace("-", "_")
    return any(part in lowered for part in SENSITIVE_PARTS)


def mask_values(value: Any) -> Any:
    """Drop secrets and replace email addresses with the HMAC hex digest."""
    if isinstance(value, Mapping):
        masked: dict[str, Any] = {}
        for key, item in value.items():
            name = str(key)
            if _sensitive_key(name):
                continue
            if name.lower() in {"email", "e-mail", "email_address"}:
                if isinstance(item, str):
                    masked[name] = {"email_hash": _safe_email_hash(item)}
                continue
            masked[name] = mask_values(item)
        return masked
    if isinstance(value, list):
        return [mask_values(item) for item in value]
    if isinstance(value, str):
        return _scrub_fragment(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _scrub_fragment(str(value))


def _json_text(value: Mapping | None) -> str | None:
    if value is None:
        return None
    masked = mask_values(dict(value))
    encoded = json.dumps(masked, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    encoded = _scrub_fragment(encoded)
    if len(encoded) > MAX_VALUE_CHARS:
        encoded = '{"omitted":true}'
    return encoded


def _client_ip(request: Request | None) -> str | None:
    if request is None or request.client is None:
        return None
    host = request.client.host or ""
    host = host.strip()
    if not host:
        return None
    return host[:64]


def _user_agent(request: Request | None) -> str | None:
    if request is None:
        return None
    raw = request.headers.get("user-agent", "")
    cleaned = _scrub_fragment(raw).replace("\r", " ").replace("\n", " ").strip()
    if not cleaned:
        return None
    return cleaned[:256]


def _request_id(request: Request | None, explicit: str | None) -> str:
    if explicit and REQUEST_ID_RE.fullmatch(explicit):
        return explicit
    if request is not None:
        raw = request.headers.get("x-request-id", "")
        if REQUEST_ID_RE.fullmatch(raw):
            return raw
    return uuid.uuid4().hex


def _session_id_from_request(request: Request | None) -> int | None:
    if request is None:
        return None
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    token = header.split(" ", 1)[1].strip()
    secret = os.getenv("JWT_SECRET_KEY")
    if not token or not secret:
        return None
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
            options={"verify_exp": False, "verify_iat": False, "verify_nbf": False},
        )
        return int(payload["sid"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        return None


def _check_action(action: str) -> str:
    if not isinstance(action, str) or not ACTION_RE.fullmatch(action):
        raise ValueError("unknown audit action")
    return action


def _check_email_hash(email_hash: str | None) -> str | None:
    if email_hash is None:
        return None
    if not HEX_HASH_RE.fullmatch(email_hash):
        raise ValueError("email_hash must be a hex digest")
    return email_hash


def _lock_and_previous(db: Session) -> str:
    """Serialise inserts and return the previous entry hash, or ''."""
    with db.no_autoflush:
        updated = db.execute(text("UPDATE audit_chain_lock SET guard = guard + 1 WHERE id = 1"))
        if updated.rowcount != 1:
            raise RuntimeError("audit_chain_lock is missing. Run alembic upgrade head.")
        pending = [obj for obj in db.new if isinstance(obj, AuditLog) and obj.entry_hash]
        if pending:
            return pending[-1].entry_hash
        latest = db.execute(
            text("SELECT entry_hash FROM audit_log ORDER BY id DESC LIMIT 1")
        ).scalar()
    return latest or ""


def record_event(
    db: Session,
    *,
    action: str,
    actor_user_id: int | None = None,
    actor_role: str | None = None,
    session_id: int | None = None,
    request_id: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    circle_id: int | None = None,
    target_user_id: int | None = None,
    email: str | None = None,
    email_hash: str | None = None,
    before: Mapping | None = None,
    after: Mapping | None = None,
    at: datetime | None = None,
    request: Request | None = None,
) -> AuditLog:
    """Append one audit row. Does not commit.

    ``email`` is hashed and discarded. A caller that already has the HMAC
    passes ``email_hash`` and does not pass the address.
    """
    action = _check_action(action)
    if email:
        email_hash = _safe_email_hash(email)
    email_hash = _check_email_hash(email_hash)
    req = request if request is not None else current_request()
    moment = at or clock_now()
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    if session_id is None:
        session_id = _session_id_from_request(req)
    if ip is None:
        ip = _client_ip(req)
    if user_agent is None:
        user_agent = _user_agent(req)
    if actor_role is not None:
        actor_role = _scrub_fragment(str(actor_role))[:32] or None
    before_text = _json_text(before)
    after_text = _json_text(after)
    material = {
        "action": action,
        "actor_role": actor_role,
        "actor_user_id": actor_user_id,
        "after": after_text,
        "before": before_text,
        "circle_id": circle_id,
        "created_at": _iso(moment),
        "email_hash": email_hash,
        "ip": ip,
        "request_id": _request_id(req, request_id),
        "session_id": session_id,
        "target_user_id": target_user_id,
        "user_agent": user_agent,
    }
    previous = _lock_and_previous(db)
    canonical = _canonical_json(previous, material)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    row = AuditLog(
        created_at=moment,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        session_id=session_id,
        request_id=material["request_id"],
        ip=ip,
        user_agent=user_agent,
        circle_id=circle_id,
        action=action,
        target_user_id=target_user_id,
        email_hash=email_hash,
        before_values=before_text,
        after_values=after_text,
        prev_hash=previous or None,
        entry_hash=digest,
        canonical=canonical,
    )
    db.add(row)
    return row


def record_lockout(
    db: Session,
    *,
    action: str,
    email: str | None = None,
    email_hash: str | None = None,
    user_id: int | None = None,
    request: Request | None = None,
) -> AuditLog:
    """Record an account lockout. The address is stored only as an HMAC."""
    if action not in {"login", "password_reset", "resend_verification"}:
        raise ValueError("unknown lockout action")
    return record_event(
        db,
        action="account_locked",
        actor_user_id=user_id,
        target_user_id=user_id,
        email=email,
        email_hash=email_hash,
        request=request,
        after={"auth_action": action},
    )


def write_auth_audit(
    db: Session,
    *,
    action: str,
    email: str | None = None,
    user_id: int | None = None,
    session_id: int | None = None,
    actor_role: str | None = None,
    request: Request | None = None,
) -> AuthAuditEvent:
    """Write the legacy auth audit row. Flush copies it into ``audit_log``."""
    req = request if request is not None else current_request()
    row = AuthAuditEvent(
        created_at=clock_now(),
        action=_check_action(action),
        user_id=user_id,
        email_hash=_safe_email_hash(email),
        ip=_client_ip(req),
    )
    row.audit_session_id = session_id
    row.audit_actor_role = actor_role
    db.add(row)
    return row


def _canonical_json(previous: str, material: dict) -> str:
    """Exact bytes that ``entry_hash`` covers, including the previous hash."""
    body = {"prev": previous, **material}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _material_from_row(row: AuditLog) -> dict:
    """Rebuild the hashed record from the stored columns, not from ``canonical``."""
    return {
        "action": row.action,
        "actor_role": row.actor_role,
        "actor_user_id": row.actor_user_id,
        "after": row.after_values,
        "before": row.before_values,
        "circle_id": row.circle_id,
        "created_at": _iso(row.created_at),
        "email_hash": row.email_hash,
        "ip": row.ip,
        "request_id": row.request_id,
        "session_id": row.session_id,
        "target_user_id": row.target_user_id,
        "user_agent": row.user_agent,
    }


def verify_chain(db: Session) -> bool:
    """True when every column, the stored canonical copy, and the hash chain agree.

    Each row is rebuilt from its columns and the previous row's hash. That JSON
    must match the stored ``canonical`` byte for byte. Its SHA-256 must match
    ``entry_hash``, and ``prev_hash`` must be the previous row's ``entry_hash``.
    """
    rows = db.query(AuditLog).order_by(AuditLog.id).all()
    previous = ""
    for row in rows:
        if row.canonical is None:
            return False
        rebuilt = _canonical_json(previous, _material_from_row(row))
        if rebuilt != row.canonical:
            return False
        digest = hashlib.sha256(rebuilt.encode("utf-8")).hexdigest()
        if digest != row.entry_hash:
            return False
        if row.prev_hash != (previous or None):
            return False
        previous = row.entry_hash
    return True


def is_platform_admin(user: User) -> bool:
    """True only when the stored platform role is platform admin."""
    return user.platform_role == PLATFORM_ADMIN


def grant_platform_admin(db: Session, *, user_id: int, actor_user_id: int | None) -> None:
    """Grant platform admin. There is no HTTP route for this. The caller commits."""
    user = db.get(User, user_id)
    if user is None:
        raise ValueError("user not found")
    before = user.platform_role
    if before == PLATFORM_ADMIN:
        return
    user.platform_role = PLATFORM_ADMIN
    record_event(
        db,
        action="platform_role_changed",
        actor_user_id=actor_user_id,
        actor_role=PLATFORM_ADMIN if actor_user_id is not None else None,
        target_user_id=user_id,
        before={"platform_role": before},
        after={"platform_role": PLATFORM_ADMIN},
    )


def _mirrored_action(action: str) -> tuple[str, dict | None]:
    if action.endswith("_lockout") and ACTION_RE.fullmatch(action):
        source = action[: -len("_lockout")]
        return "account_locked", {"auth_action": source}
    return action, None


@event.listens_for(Session, "before_flush")
def _mirror_auth_audit(session: Session, _flush_context, _instances) -> None:
    """Copy auth audit rows into the hash chain in the same transaction."""
    pending = [
        obj
        for obj in list(session.new)
        if isinstance(obj, AuthAuditEvent) and not getattr(obj, "_mirrored_to_audit_log", False)
    ]
    for obj in pending:
        obj._mirrored_to_audit_log = True
        action, extra = _mirrored_action(obj.action)
        if not ACTION_RE.fullmatch(action):
            continue
        after = getattr(obj, "audit_after", None)
        if after is None:
            after = extra
        record_event(
            session,
            action=action,
            actor_user_id=obj.user_id,
            actor_role=getattr(obj, "audit_actor_role", None),
            session_id=getattr(obj, "audit_session_id", None),
            target_user_id=obj.user_id,
            email_hash=obj.email_hash,
            ip=obj.ip,
            at=obj.created_at,
            after=after,
        )


@event.listens_for(AuditLog, "before_update")
def _reject_audit_update(_mapper, _connection, _target) -> None:
    raise PermissionError("audit_log is append-only")


@event.listens_for(AuditLog, "before_delete")
def _reject_audit_delete(_mapper, _connection, _target) -> None:
    raise PermissionError("audit_log is append-only")


@dataclass(frozen=True)
class AuditFilters:
    user_id: int | None
    circle_id: int | None
    event_type: str | None
    start: datetime | None
    end_before: datetime | None
    before_id: int | None
    after_id: int | None
    page_size: int
    start_raw: str
    end_raw: str


def _parse_bound(value: str, *, end: bool) -> datetime:
    text_value = value.strip()
    if not text_value:
        raise ValueError("empty date")
    date_only = re.fullmatch(r"\d{4}-\d{2}-\d{2}", text_value) is not None
    try:
        parsed = datetime.fromisoformat(text_value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid date") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    if date_only and end:
        return parsed + timedelta(days=1)
    if date_only:
        return parsed
    if end:
        return parsed + timedelta(microseconds=1)
    return parsed


def parse_filters(params: Mapping[str, str]) -> AuditFilters:
    """Read list filters. A bad value is a 422, not a filter bypass.

    Pages are a keyset on ``id``. ``before_id`` returns older rows. ``after_id``
    returns the next newer rows. Offset ``page`` is ignored so a logged read
    cannot shift the next page onto a row the caller already saw.
    """
    try:
        page_size = int(params.get("page_size", "50"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Page size must be a number.") from exc
    if page_size < 1 or page_size > MAX_PAGE_SIZE:
        raise HTTPException(status_code=422, detail="Page size must be from 1 to 100.")

    def optional_id(name: str) -> int | None:
        raw = params.get(name, "").strip()
        if not raw:
            return None
        try:
            number = int(raw)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"{name} must be a number.") from exc
        if number < 1:
            raise HTTPException(status_code=422, detail=f"{name} must be a number.")
        return number

    event_type = params.get("event_type", "").strip()
    if event_type and not ACTION_RE.fullmatch(event_type):
        raise HTTPException(status_code=422, detail="Unknown event type.")
    start_raw = params.get("start", "").strip()
    end_raw = params.get("end", "").strip()
    try:
        start = _parse_bound(start_raw, end=False) if start_raw else None
        end_before = _parse_bound(end_raw, end=True) if end_raw else None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Use an ISO date.") from exc
    if start is not None and end_before is not None and start >= end_before:
        raise HTTPException(status_code=422, detail="The start is after the end.")
    before_id = optional_id("before_id")
    after_id = optional_id("after_id")
    if before_id is not None and after_id is not None:
        raise HTTPException(status_code=422, detail="Pass before_id or after_id, not both.")
    return AuditFilters(
        user_id=optional_id("user_id"),
        circle_id=optional_id("circle_id"),
        event_type=event_type or None,
        start=start,
        end_before=end_before,
        before_id=before_id,
        after_id=after_id,
        page_size=page_size,
        start_raw=start_raw,
        end_raw=end_raw,
    )


def query_entries(db: Session, filters: AuditFilters) -> tuple[list[AuditLog], int]:
    query = db.query(AuditLog)
    if filters.user_id is not None:
        query = query.filter(
            or_(
                AuditLog.actor_user_id == filters.user_id,
                AuditLog.target_user_id == filters.user_id,
            )
        )
    if filters.circle_id is not None:
        query = query.filter(AuditLog.circle_id == filters.circle_id)
    if filters.event_type is not None:
        query = query.filter(AuditLog.action == filters.event_type)
    if filters.start is not None:
        query = query.filter(AuditLog.created_at >= filters.start)
    if filters.end_before is not None:
        query = query.filter(AuditLog.created_at < filters.end_before)
    total = query.count()
    if filters.before_id is not None:
        query = query.filter(AuditLog.id < filters.before_id)
        rows = query.order_by(AuditLog.id.desc()).limit(filters.page_size).all()
    elif filters.after_id is not None:
        rows = (
            query.filter(AuditLog.id > filters.after_id)
            .order_by(AuditLog.id.asc())
            .limit(filters.page_size)
            .all()
        )
        rows.reverse()
    else:
        rows = query.order_by(AuditLog.id.desc()).limit(filters.page_size).all()
    return rows, total


def entry_payload(row: AuditLog) -> dict:
    def load_json(raw: str | None):
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    return {
        "id": row.id,
        "created_at": _iso(row.created_at),
        "action": row.action,
        "actor_user_id": row.actor_user_id,
        "actor_role": row.actor_role,
        "session_id": row.session_id,
        "request_id": row.request_id,
        "ip": row.ip,
        "user_agent": row.user_agent,
        "circle_id": row.circle_id,
        "target_user_id": row.target_user_id,
        "email_hash": row.email_hash,
        "before": load_json(row.before_values),
        "after": load_json(row.after_values),
        "prev_hash": row.prev_hash,
        "entry_hash": row.entry_hash,
    }


def _record_view(db: Session, user: User, filters: AuditFilters, *, view: str, allowed: bool) -> None:
    record_event(
        db,
        action="audit_log_read" if allowed else "audit_log_denied",
        actor_user_id=user.id,
        actor_role=PLATFORM_ADMIN if allowed else None,
        target_user_id=filters.user_id,
        circle_id=filters.circle_id,
        after={
            "view": view,
            "before_id": filters.before_id,
            "after_id": filters.after_id,
            "page_size": filters.page_size,
            "event_type": filters.event_type,
            "allowed": allowed,
        },
    )
    db.commit()


def _require_reader(db: Session, user: User, view: str) -> None:
    """403 unless the stored platform role allows the read. The client role is ignored."""
    if is_platform_admin(user):
        return
    record_event(
        db,
        action="audit_log_denied",
        actor_user_id=user.id,
        after={"view": view, "allowed": False},
    )
    db.commit()
    raise HTTPException(status_code=403, detail=NOT_ALLOWED)


def _render_page(rows: list[AuditLog], total: int, filters: AuditFilters) -> str:
    def cell(value: object) -> str:
        if value is None or value == "":
            return ""
        return html.escape(str(value), quote=True)

    body_rows = []
    for row in rows:
        short_hash = ""
        if row.email_hash:
            short_hash = row.email_hash[:12] + "…"
        body_rows.append(
            "<tr>"
            f"<td>{cell(row.id)}</td>"
            f"<td>{cell(_iso(row.created_at))}</td>"
            f"<td>{cell(row.action)}</td>"
            f"<td>{cell(row.actor_user_id)}</td>"
            f"<td>{cell(row.actor_role)}</td>"
            f"<td>{cell(row.target_user_id)}</td>"
            f"<td>{cell(row.circle_id)}</td>"
            f"<td>{cell(row.session_id)}</td>"
            f"<td>{cell(short_hash)}</td>"
            f"<td>{cell(row.ip)}</td>"
            "</tr>"
        )
    if not body_rows:
        body_rows.append('<tr><td colspan="10">No entries.</td></tr>')
    def page_href(cursor_name: str, cursor: int) -> str:
        query = {
            "user_id": "" if filters.user_id is None else str(filters.user_id),
            "circle_id": "" if filters.circle_id is None else str(filters.circle_id),
            "event_type": filters.event_type or "",
            "start": filters.start_raw,
            "end": filters.end_raw,
            cursor_name: str(cursor),
            "page_size": str(filters.page_size),
        }
        return "/admin/audit?" + "&".join(
            f"{html.escape(key, quote=True)}={html.escape(value, quote=True)}"
            for key, value in query.items()
        )

    newest_id = rows[0].id if rows else None
    oldest_id = rows[-1].id if rows else None
    prev_link = ""
    next_link = ""
    if newest_id is not None and (filters.before_id is not None or filters.after_id is not None):
        prev_link = f'<a href="{page_href("after_id", newest_id)}">Newer</a>'
    if oldest_id is not None and len(rows) == filters.page_size:
        next_link = f'<a href="{page_href("before_id", oldest_id)}">Older</a>'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Audit log</title>
<style>
body {{ font-family: Georgia, "Times New Roman", serif; margin: 2rem; color: #1c1915; background: #f7f4ee; }}
h1 {{ font-weight: normal; }}
form {{ display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: end; margin: 1rem 0 1.5rem; }}
label {{ display: flex; flex-direction: column; font-size: 0.85rem; gap: 0.25rem; }}
input {{ font: inherit; padding: 0.35rem 0.5rem; border: 1px solid #c9c1b4; background: #fff; }}
button {{ font: inherit; padding: 0.4rem 0.8rem; background: #1c1915; color: #f7f4ee; border: 0; }}
table {{ width: 100%; border-collapse: collapse; background: #fff; }}
th, td {{ text-align: left; padding: 0.45rem 0.55rem; border-bottom: 1px solid #e4ddd2; font-size: 0.9rem; }}
.note {{ color: #5c564c; }}
.pager {{ display: flex; gap: 1rem; margin-top: 1rem; }}
</style>
</head>
<body>
<h1>Audit log</h1>
<p class="note">Read-only. Personal details are masked. This view is itself recorded.</p>
<form method="get" action="/admin/audit">
<label>User id<input name="user_id" value="{cell(filters.user_id or "")}"></label>
<label>Circle id<input name="circle_id" value="{cell(filters.circle_id or "")}"></label>
<label>Event type<input name="event_type" value="{cell(filters.event_type or "")}"></label>
<label>Start<input name="start" value="{cell(filters.start_raw)}" placeholder="2026-10-18"></label>
<label>End<input name="end" value="{cell(filters.end_raw)}" placeholder="2026-10-18"></label>
<label>Page size<input name="page_size" value="{cell(filters.page_size)}"></label>
<button type="submit">Filter</button>
</form>
<table>
<thead><tr><th>Id</th><th>When (UTC)</th><th>Event</th><th>Actor</th><th>Role</th><th>Target</th><th>Circle</th><th>Session</th><th>Email hash</th><th>IP</th></tr></thead>
<tbody>
{"".join(body_rows)}
</tbody>
</table>
<p class="pager">{prev_link}<span>{total} entries</span>{next_link}</p>
</body>
</html>
"""


def register_audit_routes(fastapi_app: FastAPI, get_current_user) -> None:
    """Platform-admin read API and page. No create, update, or delete route."""

    @fastapi_app.get("/api/v1/admin/audit")
    def list_audit(
        request: Request,
        response: Response,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "no-store"
        _require_reader(db, user, "api")
        filters = parse_filters(request.query_params)
        rows, total = query_entries(db, filters)
        _record_view(db, user, filters, view="api", allowed=True)
        return {
            "entries": [entry_payload(row) for row in rows],
            "page_size": filters.page_size,
            "total": total,
            "before_id": rows[-1].id if rows else None,
            "after_id": rows[0].id if rows else None,
        }

    @fastapi_app.get("/admin/audit")
    def audit_page(
        request: Request,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        _require_reader(db, user, "page")
        filters = parse_filters(request.query_params)
        rows, total = query_entries(db, filters)
        _record_view(db, user, filters, view="page", allowed=True)
        page = _render_page(rows, total, filters)
        return HTMLResponse(page, headers={"Cache-Control": "no-store"})
