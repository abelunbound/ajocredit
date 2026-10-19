"""Read-only platform-admin ledger view (#117).

Synthetic @example.test users only. Balances are derived from lines.
A circle admin is refused. Viewing writes an audit row at clock.now().
"""

from __future__ import annotations

import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("JWT_SECRET_KEY", "test-only-jwt-secret-key-32chars!!")
os.environ["ALLOW_LOCAL_STUB_LOGIN"] = "false"
os.environ["SEED_DEMO_ACCOUNTS"] = "false"
os.environ.setdefault("AJO_ENV", "local")
os.environ.setdefault("EMAIL_SENDER", "dev")
os.environ.setdefault("AUDIT_EMAIL_HMAC_KEY", "test-only-audit-email-hmac-key")

if "api" not in sys.modules:
    _configured_url = os.environ.get("DATABASE_URL", "")
    if not _configured_url.startswith("postgres"):
        _db_dir = tempfile.mkdtemp(prefix="ajo-ledger-admin-")
        os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_db_dir) / "ajo.db")
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")

import pytest
from alembic.script import ScriptDirectory
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

import api
import clock
import database
import mail
from database import AuditLog, User
from ledger import (
    CREDIT,
    DEBIT,
    LedgerAccount,
    LedgerEntry,
    LedgerLine,
    Posting,
    format_pence,
    open_account,
    post_entry,
    post_reversal,
)

client = TestClient(api.app)
PASSWORD = "correct-horse"
REPO = Path(__file__).resolve().parents[1]
HEAD = "0008_audit_log"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("AJO_ENV", "local")
    monkeypatch.setenv("EMAIL_SENDER", "dev")
    clock.reset()
    mail.clear_memory_inbox()
    yield
    clock.reset()
    mail.clear_memory_inbox()


def _email() -> str:
    return f"ledger-{uuid.uuid4().hex}@example.test"


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _verified_user(name: str = "Ada Test") -> tuple[str, str]:
    email = _email()
    created = client.post(
        "/api/v1/auth/signup",
        json={"name": name, "email": email, "password": PASSWORD},
    )
    assert created.status_code == 201, created.text
    body = mail.memory_inbox()[-1]["body"]
    token = body.split("/verify-email#", 1)[1].split()[0].strip()
    confirmed = client.post("/api/v1/auth/verification/confirm", json={"token": token})
    assert confirmed.status_code == 200, confirmed.text
    logged_in = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert logged_in.status_code == 200, logged_in.text
    return email, logged_in.json()["access_token"]


def _grant_platform_admin(email: str) -> None:
    db = database.SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        user.platform_role = "platform_admin"
        db.commit()
    finally:
        db.close()


def _suffix() -> str:
    return uuid.uuid4().hex[:12]


def _post_contribution(circle: str, member: str, pence: int, *, reference: str, description: str) -> None:
    db = database.SessionLocal()
    try:
        asset_code = f"asset:partner:{circle}"
        liability_code = f"liability:{member}:{circle}"
        if db.query(LedgerAccount).filter(LedgerAccount.code == asset_code).one_or_none() is None:
            open_account(
                db,
                code=asset_code,
                name="Partner clearing",
                kind="asset",
                circle_ref=circle,
            )
        if db.query(LedgerAccount).filter(LedgerAccount.code == liability_code).one_or_none() is None:
            open_account(
                db,
                code=liability_code,
                name=f"Contributions {member}",
                kind="liability",
                circle_ref=circle,
                member_ref=member,
            )
        post_entry(
            db,
            description=description,
            reference=reference,
            postings=[
                Posting(asset_code, DEBIT, pence),
                Posting(liability_code, CREDIT, pence),
            ],
        )
        db.commit()
    finally:
        db.close()


def _counts() -> tuple[int, int, int]:
    db = database.SessionLocal()
    try:
        return (
            db.query(LedgerAccount).count(),
            db.query(LedgerEntry).count(),
            db.query(LedgerLine).count(),
        )
    finally:
        db.close()


def _views(user_email: str) -> list[AuditLog]:
    db = database.SessionLocal()
    try:
        user = db.query(User).filter(User.email == user_email).one()
        return (
            db.query(AuditLog)
            .filter(AuditLog.actor_user_id == user.id, AuditLog.action == "financial_data_viewed")
            .order_by(AuditLog.id)
            .all()
        )
    finally:
        db.close()


def test_format_pence_uses_integers_only():
    assert format_pence(2575) == "£25.75"
    assert format_pence(0) == "£0.00"
    assert format_pence(-50) == "-£0.50"
    assert format_pence(100, "GBP") == "£1.00"


def test_alembic_head_is_single():
    script = ScriptDirectory.from_config(Config(str(REPO / "alembic.ini")))
    assert script.get_heads() == [HEAD]


def test_platform_role_rejects_other_values():
    email, _token = _verified_user()
    db = database.SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).one()
        user.platform_role = "admin"
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


def test_circle_admin_and_member_are_denied_and_client_role_is_ignored():
    admin_email, admin_token = _verified_user("Amina Test")
    _member_email, member_token = _verified_user("Tunde Test")
    created = client.post(
        "/api/v1/circles",
        headers=_auth(admin_token),
        json={"name": "Ledger Gate", "role": "member"},
    )
    assert created.status_code == 201, created.text
    circle_id = created.json()["circle_id"]
    joined = client.post(
        f"/api/v1/circles/{circle_id}/join",
        headers=_auth(member_token),
        json={"role": "admin"},
    )
    assert joined.status_code == 200, joined.text

    circle = f"circle-synth-{_suffix()}"
    _post_contribution(circle, "member-ada", 2575, reference=f"ref-{_suffix()}", description="Ada pays in")
    before = _counts()

    denied = client.get(
        "/api/v1/admin/ledger",
        headers={**_auth(admin_token), "X-Role": "platform_admin"},
        params={"role": "platform_admin", "circle": circle},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Not allowed."
    assert circle not in denied.text
    assert "2575" not in denied.text
    assert "Ada pays in" not in denied.text

    member_denied = client.get(
        "/admin/ledger",
        headers={**_auth(member_token), "X-Role": "admin"},
        params={"role": "admin"},
    )
    assert member_denied.status_code == 403
    assert "Ada pays in" not in member_denied.text
    missing = client.get("/api/v1/admin/ledger")
    assert missing.status_code == 401
    assert _counts() == before
    assert _views(admin_email) == []


def test_platform_admin_sees_derived_balances_and_both_sides_of_an_entry():
    circle = f"circle-synth-{_suffix()}"
    other = f"circle-synth-{_suffix()}"
    when = datetime(2026, 4, 2, 15, 30, tzinfo=timezone.utc)
    clock.freeze(when)
    _post_contribution(
        circle,
        "member-ada",
        2575,
        reference=f"ref-{_suffix()}",
        description="Ada pays in <script>",
    )
    _post_contribution(
        other,
        "member-tunde",
        1000,
        reference=f"ref-{_suffix()}",
        description="Tunde pays in",
    )
    before = _counts()
    viewed_at = datetime(2026, 4, 3, 8, 0, tzinfo=timezone.utc)
    clock.freeze(viewed_at)
    email, token = _verified_user()
    _grant_platform_admin(email)

    response = client.get(
        "/api/v1/admin/ledger",
        headers={**_auth(token), "X-Role": "member"},
        params={"role": "member", "circle": circle},
    )
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    codes = {row["code"]: row for row in body["balances"]}
    assert set(codes) == {
        f"asset:partner:{circle}",
        f"liability:member-ada:{circle}",
    }
    assert codes[f"asset:partner:{circle}"]["balance_pence"] == 2575
    assert codes[f"asset:partner:{circle}"]["balance_display"] == "£25.75"
    assert isinstance(codes[f"asset:partner:{circle}"]["balance_pence"], int)
    assert codes[f"liability:member-ada:{circle}"]["balance_pence"] == 2575
    assert codes[f"liability:member-ada:{circle}"]["member"] == "member-ada"
    assert body["total"] == 1
    assert len(body["transactions"]) == 1
    transaction = body["transactions"][0]
    assert transaction["description"] == "Ada pays in <script>"
    assert transaction["posted_at"].startswith("2026-04-02T15:30:00")
    directions = {entry["direction"]: entry for entry in transaction["entries"]}
    assert directions["debit"]["amount_pence"] == 2575
    assert directions["credit"]["amount_display"] == "£25.75"
    assert directions["debit"]["amount_pence"] + (
        -directions["credit"]["amount_pence"]
    ) == 0
    assert "balance" not in {column.name for column in LedgerAccount.__table__.columns}
    assert _counts() == before

    views = _views(email)
    assert len(views) == 1
    assert views[0].action == "financial_data_viewed"
    assert views[0].email_hash is None
    stored = views[0].created_at
    if stored.tzinfo is None:
        stored = stored.replace(tzinfo=timezone.utc)
    assert stored.astimezone(timezone.utc) == viewed_at
    assert "password" not in response.text
    assert PASSWORD not in response.text


def test_filters_pagination_and_reversal_move_the_derived_balance():
    circle = f"circle-synth-{_suffix()}"
    clock.freeze(datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc))
    first_ref = f"ref-{_suffix()}"
    _post_contribution(circle, "member-ada", 2575, reference=first_ref, description="May contribution")
    clock.freeze(datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc))
    _post_contribution(
        circle,
        "member-tunde",
        5000,
        reference=f"ref-{_suffix()}",
        description="June contribution",
    )
    clock.freeze(datetime(2026, 6, 2, 10, 0, tzinfo=timezone.utc))
    _post_contribution(
        circle,
        "member-ada",
        100,
        reference=f"ref-{_suffix()}",
        description="June top up",
    )
    email, token = _verified_user()
    _grant_platform_admin(email)

    may = client.get(
        "/api/v1/admin/ledger",
        headers=_auth(token),
        params={"circle": circle, "start": "2026-05-01", "end": "2026-05-31"},
    )
    assert may.status_code == 200, may.text
    may_body = may.json()
    assert may_body["total"] == 1
    assert may_body["transactions"][0]["description"] == "May contribution"
    may_balances = {row["member"]: row["balance_pence"] for row in may_body["balances"] if row["member"]}
    assert may_balances["member-ada"] == 2575
    assert may_balances["member-tunde"] == 0

    ada = client.get(
        "/api/v1/admin/ledger",
        headers=_auth(token),
        params={"circle": circle, "member": "member-ada", "account_type": "liability"},
    )
    assert ada.status_code == 200, ada.text
    ada_body = ada.json()
    assert [row["code"] for row in ada_body["balances"]] == [f"liability:member-ada:{circle}"]
    assert ada_body["balances"][0]["balance_pence"] == 2675
    assert ada_body["total"] == 2
    assert all(
        any(entry["member"] == "member-ada" for entry in transaction["entries"])
        for transaction in ada_body["transactions"]
    )

    page = client.get(
        "/api/v1/admin/ledger",
        headers=_auth(token),
        params={"circle": circle, "page": 1, "page_size": 1},
    )
    assert page.status_code == 200, page.text
    assert page.json()["total"] == 3
    assert page.json()["transactions"][0]["description"] == "June top up"
    page_two = client.get(
        "/api/v1/admin/ledger",
        headers=_auth(token),
        params={"circle": circle, "page": 2, "page_size": 1},
    )
    assert page_two.json()["transactions"][0]["description"] == "June contribution"

    db = database.SessionLocal()
    try:
        original = db.query(LedgerEntry).filter(LedgerEntry.reference == first_ref).one()
        post_reversal(db, original.id, reference=f"rev-{_suffix()}")
        db.commit()
    finally:
        db.close()

    after = client.get(
        "/api/v1/admin/ledger",
        headers=_auth(token),
        params={"circle": circle, "member": "member-ada", "account_type": "liability"},
    )
    assert after.status_code == 200, after.text
    assert after.json()["balances"][0]["balance_pence"] == 100

    bad_type = client.get(
        "/api/v1/admin/ledger",
        headers=_auth(token),
        params={"account_type": "owner"},
    )
    assert bad_type.status_code == 422
    bad_page = client.get("/api/v1/admin/ledger", headers=_auth(token), params={"page": 0})
    assert bad_page.status_code == 422
    bad_size = client.get(
        "/api/v1/admin/ledger",
        headers=_auth(token),
        params={"page_size": 101},
    )
    assert bad_size.status_code == 422
    bad_range = client.get(
        "/api/v1/admin/ledger",
        headers=_auth(token),
        params={"start": "2026-06-02", "end": "2026-05-01"},
    )
    assert bad_range.status_code == 422


def test_page_is_read_only_html_and_writes_are_rejected():
    circle = f"circle-synth-{_suffix()}"
    clock.freeze(datetime(2026, 7, 4, 9, 0, tzinfo=timezone.utc))
    _post_contribution(circle, "member-ada", 2575, reference=f"ref-{_suffix()}", description="Page contribution")
    email, token = _verified_user()
    _grant_platform_admin(email)
    before = _counts()
    page = client.get("/admin/ledger", headers=_auth(token), params={"circle": circle, "page_size": 10})
    assert page.status_code == 200, page.text
    assert page.headers["content-type"].startswith("text/html")
    assert "£25.75" in page.text
    assert ">2575<" in page.text
    assert "Page contribution" in page.text
    assert 'method="get"' in page.text
    assert 'method="post"' not in page.text.lower()
    assert ">Delete<" not in page.text
    assert ">Edit<" not in page.text
    assert "Read-only" in page.text
    assert _counts() == before

    for method in ("post", "put", "patch", "delete"):
        api_response = getattr(client, method)("/api/v1/admin/ledger", headers=_auth(token))
        page_response = getattr(client, method)("/admin/ledger", headers=_auth(token))
        assert api_response.status_code == 405
        assert page_response.status_code == 405
    assert _counts() == before

    schema = client.get("/openapi.json").json()
    assert set(schema["paths"]["/api/v1/admin/ledger"]) == {"get"}
    assert set(schema["paths"]["/admin/ledger"]) == {"get"}


def test_html_escapes_description():
    email, token = _verified_user()
    _grant_platform_admin(email)
    circle = f"circle-synth-{_suffix()}"
    _post_contribution(
        circle,
        "member-ada",
        10,
        reference=f"ref-{_suffix()}",
        description="Note <script>alert(1)</script>",
    )
    page = client.get("/admin/ledger", headers=_auth(token), params={"circle": circle})
    assert page.status_code == 200, page.text
    assert "<script>alert" not in page.text
    assert "&lt;script&gt;" in page.text
