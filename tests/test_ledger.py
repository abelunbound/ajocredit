"""Ledger schema, append-only guards, and double-entry postings.

Synthetic accounts only. No real member data.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_configured_url = os.environ.get("DATABASE_URL", "")
USING_POSTGRES = _configured_url.startswith("postgres")
if not USING_POSTGRES:
    _db_dir = tempfile.mkdtemp(prefix="ajo-ledger-")
    os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_db_dir) / "ajo.db")

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import SQLAlchemyError

import clock
import database
import ledger
from database import normalize_database_url
from ledger import (
    CREDIT,
    DEBIT,
    LedgerAccount,
    LedgerAppendOnlyError,
    LedgerEntry,
    LedgerLine,
    LedgerPostingError,
    Posting,
    account_balance_pence,
    assert_ledger_balanced,
    open_account,
    post_entry,
    post_reversal,
)

_ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
_config = Config(str(_ALEMBIC_INI))
command.upgrade(_config, "head")


def setup_function() -> None:
    clock.restore_for_tests()


def teardown_function() -> None:
    clock.restore_for_tests()


def _suffix() -> str:
    return uuid.uuid4().hex


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _session():
    return database.SessionLocal()


def _open_pair(db, suffix: str | None = None):
    suffix = suffix or _suffix()
    circle = f"circle-synth-{suffix}"
    cash = open_account(
        db,
        code=f"asset:partner:{circle}",
        name="Partner clearing",
        kind="asset",
        circle_ref=circle,
    )
    member = open_account(
        db,
        code=f"liability:member-ada:{circle}",
        name="Member Ada contributions",
        kind="liability",
        circle_ref=circle,
        member_ref="member-ada",
    )
    return cash, member


def test_head_revision_is_the_ledger_migration():
    script = ScriptDirectory.from_config(_config)
    head = script.get_current_head()
    revision = script.get_revision(head)
    assert revision is not None
    assert revision.revision == "0002_create_ledger"
    assert revision.down_revision == "0001_create_users"


def test_money_columns_are_integers_not_floats():
    from sqlalchemy import Float, Numeric

    amount = LedgerLine.__table__.c.amount_pence
    assert amount.type.__class__.__name__ == "BigInteger"
    assert not isinstance(amount.type, (Float, Numeric))
    for table in (LedgerAccount, LedgerEntry, LedgerLine):
        for column in table.__table__.columns:
            assert not isinstance(column.type, (Float, Numeric))

    with database.engine.connect() as connection:
        if database.engine.dialect.name == "sqlite":
            rows = connection.exec_driver_sql("PRAGMA table_info(ledger_lines)").all()
            stored = next(row[2] for row in rows if row[1] == "amount_pence")
            assert "INT" in stored.upper()
        else:
            stored = connection.exec_driver_sql(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name = 'ledger_lines' AND column_name = 'amount_pence'"
            ).scalar()
            assert stored == "bigint"


def test_migration_upgrades_and_downgrades(tmp_path, monkeypatch):
    url = "sqlite:///" + str(tmp_path / "ledger-migration.db")
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = Config(str(_ALEMBIC_INI))
    command.upgrade(cfg, "head")

    engine = create_engine(url)
    names = set(inspect(engine).get_table_names())
    assert {"users", "ledger_accounts", "ledger_entries", "ledger_lines"} <= names
    with engine.connect() as connection:
        triggers = {
            row[0]
            for row in connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type = 'trigger'"
            ).all()
        }
    engine.dispose()
    assert "ledger_lines_append_only_update" in triggers
    assert "ledger_lines_append_only_delete" in triggers
    assert len(triggers) == 6

    command.downgrade(cfg, "0001_create_users")
    engine = create_engine(url)
    names = set(inspect(engine).get_table_names())
    assert "users" in names
    assert "ledger_accounts" not in names
    assert "ledger_entries" not in names
    assert "ledger_lines" not in names
    with engine.connect() as connection:
        triggers = connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type = 'trigger'"
        ).all()
    engine.dispose()
    assert triggers == []

    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    engine = create_engine(url)
    assert inspect(engine).get_table_names() == ["alembic_version"]
    engine.dispose()
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    names = set(inspect(engine).get_table_names())
    engine.dispose()
    assert {"users", "ledger_lines"} <= names


def test_postgres_migration_roundtrip_when_configured():
    if not USING_POSTGRES:
        pytest.skip("postgres URL not configured")
    admin_url = make_url(normalize_database_url(os.environ["DATABASE_URL"])).set(
        database="postgres"
    )
    scratch_name = "ajocredit_ledger_mig"
    scratch_url = make_url(normalize_database_url(os.environ["DATABASE_URL"])).set(
        database=scratch_name
    )
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")

    def _admin_sql(statement: str) -> None:
        with admin.connect() as connection:
            connection.exec_driver_sql(statement)

    _admin_sql(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE datname = 'ajocredit_ledger_mig' AND pid <> pg_backend_pid()"
    )
    _admin_sql("DROP DATABASE IF EXISTS ajocredit_ledger_mig")
    _admin_sql("CREATE DATABASE ajocredit_ledger_mig")
    try:
        os.environ["DATABASE_URL"] = scratch_url.render_as_string(hide_password=False)
        cfg = Config(str(_ALEMBIC_INI))
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "0001_create_users")
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")
        engine = create_engine(scratch_url)
        names = set(inspect(engine).get_table_names())
        with engine.connect() as connection:
            function = connection.exec_driver_sql(
                "SELECT 1 FROM pg_proc WHERE proname = 'ledger_reject_mutation'"
            ).scalar()
        engine.dispose()
        assert "ledger_lines" in names
        assert function == 1
    finally:
        os.environ["DATABASE_URL"] = _configured_url
        _admin_sql(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = 'ajocredit_ledger_mig' AND pid <> pg_backend_pid()"
        )
        _admin_sql("DROP DATABASE IF EXISTS ajocredit_ledger_mig")
        admin.dispose()


def test_balanced_posting_stores_integer_pence_and_uses_now():
    fixed = datetime(2026, 10, 18, 12, 30, tzinfo=timezone.utc)
    clock.freeze(fixed)
    db = _session()
    try:
        cash, member = _open_pair(db)
        entry = post_entry(
            db,
            description="Synthetic contribution",
            reference=f"synthetic-contrib-{_suffix()}",
            postings=[
                Posting(cash.code, DEBIT, 2575, "partner receipt"),
                Posting(member.code, CREDIT, 2575, "member ada"),
            ],
        )
        db.commit()
        db.expire_all()
        stored = db.get(LedgerEntry, entry.id)
        lines = db.query(LedgerLine).filter(LedgerLine.entry_id == entry.id).all()
        assert stored is not None
        assert _utc(stored.posted_at) == fixed
        assert _utc(db.get(LedgerAccount, cash.id).created_at) == fixed
        assert len(lines) == 2
        assert {type(line.amount_pence) for line in lines} == {int}
        assert sorted(line.amount_pence for line in lines) == [2575, 2575]
        assert account_balance_pence(db, cash) == 2575
        assert account_balance_pence(db, member) == 2575
        assert_ledger_balanced(db)
    finally:
        db.close()


def test_system_now_is_timezone_aware():
    before = datetime.now(timezone.utc) - timedelta(seconds=5)
    db = _session()
    try:
        cash, _member = _open_pair(db)
        db.commit()
        created = _utc(db.get(LedgerAccount, cash.id).created_at)
        after = datetime.now(timezone.utc) + timedelta(seconds=5)
        assert before <= created <= after
    finally:
        db.close()


def test_naive_freeze_is_rejected():
    with pytest.raises(ValueError):
        clock.freeze(datetime(2026, 1, 1))
    moment = clock.now()
    assert moment.tzinfo is not None
    assert moment.utcoffset() == timedelta(0)


def test_unbalanced_entry_is_rejected_and_not_stored():
    db = _session()
    try:
        cash, member = _open_pair(db)
        db.commit()
        before = db.query(LedgerEntry).count()
        with pytest.raises(LedgerPostingError):
            post_entry(
                db,
                description="Unbalanced synthetic",
                postings=[
                    Posting(cash.code, DEBIT, 1000),
                    Posting(member.code, CREDIT, 900),
                ],
            )
        db.rollback()
        assert db.query(LedgerEntry).count() == before
    finally:
        db.close()


def test_float_bool_and_non_positive_amounts_are_rejected():
    db = _session()
    try:
        cash, member = _open_pair(db)
        cases = [10.5, True, 0, -5, "100"]
        for amount in cases:
            with pytest.raises(LedgerPostingError):
                post_entry(
                    db,
                    description="Bad amount",
                    postings=[
                        Posting(cash.code, DEBIT, amount),
                        Posting(member.code, CREDIT, amount),
                    ],
                )
        db.rollback()
    finally:
        db.close()


def test_single_line_and_duplicate_reference_are_rejected():
    db = _session()
    try:
        cash, member = _open_pair(db)
        reference = f"synthetic-once-{_suffix()}"
        post_entry(
            db,
            description="First",
            reference=reference,
            postings=[
                Posting(cash.code, DEBIT, 100),
                Posting(member.code, CREDIT, 100),
            ],
        )
        with pytest.raises(LedgerPostingError):
            post_entry(
                db,
                description="One line",
                postings=[Posting(cash.code, DEBIT, 100)],
            )
        with pytest.raises(LedgerPostingError):
            post_entry(
                db,
                description="Again",
                reference=reference,
                postings=[
                    Posting(cash.code, DEBIT, 100),
                    Posting(member.code, CREDIT, 100),
                ],
            )
    finally:
        db.rollback()
        db.close()


def test_schema_rejects_fractional_pence_and_zero():
    db = _session()
    try:
        cash, member = _open_pair(db)
        entry = post_entry(
            db,
            description="Seed",
            postings=[
                Posting(cash.code, DEBIT, 100),
                Posting(member.code, CREDIT, 100),
            ],
        )
        db.commit()
        for amount in ("1.5", "0"):
            with pytest.raises(SQLAlchemyError):
                db.execute(
                    text(
                        "INSERT INTO ledger_lines "
                        "(entry_id, account_id, direction, amount_pence) "
                        "VALUES (:entry_id, :account_id, 'debit', :amount)"
                    ),
                    {
                        "entry_id": entry.id,
                        "account_id": cash.id,
                        "amount": amount,
                    },
                )
            db.rollback()
    finally:
        db.close()


def test_orm_update_and_delete_are_rejected():
    db = _session()
    try:
        cash, member = _open_pair(db)
        entry = post_entry(
            db,
            description="Locked",
            postings=[
                Posting(cash.code, DEBIT, 400),
                Posting(member.code, CREDIT, 400),
            ],
        )
        db.commit()
        cash_id = cash.id
        line_id = entry.lines[0].id
        original_name = cash.name
        original_amount = entry.lines[0].amount_pence

        cash.name = "Changed name"
        with pytest.raises(LedgerAppendOnlyError):
            db.commit()
        db.rollback()

        line = db.get(LedgerLine, line_id)
        db.delete(line)
        with pytest.raises(LedgerAppendOnlyError):
            db.commit()
        db.rollback()
    finally:
        db.close()

    db = _session()
    try:
        assert db.get(LedgerAccount, cash_id).name == original_name
        assert db.get(LedgerLine, line_id).amount_pence == original_amount
    finally:
        db.close()


def test_raw_update_and_delete_are_rejected_by_the_database():
    db = _session()
    try:
        cash, member = _open_pair(db)
        entry = post_entry(
            db,
            description="Trigger lock",
            postings=[
                Posting(cash.code, DEBIT, 800),
                Posting(member.code, CREDIT, 800),
            ],
        )
        db.commit()
        line_id = entry.lines[0].id
        with pytest.raises(SQLAlchemyError) as updated:
            db.execute(
                text("UPDATE ledger_lines SET amount_pence = 1 WHERE id = :id"),
                {"id": line_id},
            )
            db.commit()
        assert "append-only" in str(updated.value).lower()
        db.rollback()
        with pytest.raises(SQLAlchemyError) as deleted:
            db.execute(
                text("DELETE FROM ledger_lines WHERE id = :id"),
                {"id": line_id},
            )
            db.commit()
        assert "append-only" in str(deleted.value).lower()
        db.rollback()
        assert db.get(LedgerLine, line_id).amount_pence == 800
    finally:
        db.close()


def test_reversal_is_a_new_entry_and_leaves_the_original():
    db = _session()
    try:
        cash, member = _open_pair(db)
        entry = post_entry(
            db,
            description="Contribution to reverse",
            reference=f"synthetic-original-{_suffix()}",
            postings=[
                Posting(cash.code, DEBIT, 2575),
                Posting(member.code, CREDIT, 2575),
            ],
        )
        db.commit()
        original_id = entry.id
        original_lines = sorted((line.direction, line.amount_pence) for line in entry.lines)
        reversal = post_reversal(db, original_id, reference=f"synthetic-reversal-{_suffix()}")
        db.commit()
        db.expire_all()
        original = db.get(LedgerEntry, original_id)
        stored_lines = db.query(LedgerLine).filter(LedgerLine.entry_id == original_id).all()
        assert [(line.direction, line.amount_pence) for line in stored_lines]
        assert sorted((line.direction, line.amount_pence) for line in stored_lines) == original_lines
        assert reversal.id != original_id
        assert reversal.reversal_of_id == original_id
        assert account_balance_pence(db, cash) == 0
        assert account_balance_pence(db, member) == 0
        assert_ledger_balanced(db)
        with pytest.raises(LedgerPostingError):
            post_reversal(db, original_id)
    finally:
        db.close()


def test_synthetic_circle_contribution_and_payout_balance():
    suffix = _suffix()
    circle = f"circle-synth-{suffix}"
    db = _session()
    try:
        partner = open_account(
            db,
            code=f"asset:partner:{circle}",
            name="Partner clearing",
            kind="asset",
            circle_ref=circle,
        )
        ada = open_account(
            db,
            code=f"liability:member-ada:{circle}",
            name="Ada Example contribution",
            kind="liability",
            circle_ref=circle,
            member_ref="member-ada",
        )
        bo = open_account(
            db,
            code=f"liability:member-bo:{circle}",
            name="Bo Example contribution",
            kind="liability",
            circle_ref=circle,
            member_ref="member-bo",
        )
        post_entry(
            db,
            description="Ada Example contribution",
            reference=f"synthetic-ada-in-{suffix}",
            postings=[
                Posting(partner.code, DEBIT, 2575),
                Posting(ada.code, CREDIT, 2575),
            ],
        )
        post_entry(
            db,
            description="Bo Example contribution",
            reference=f"synthetic-bo-in-{suffix}",
            postings=[
                Posting(partner.code, DEBIT, 1800),
                Posting(bo.code, CREDIT, 1800),
            ],
        )
        post_entry(
            db,
            description="Ada Example payout",
            reference=f"synthetic-ada-out-{suffix}",
            postings=[
                Posting(ada.code, DEBIT, 2575),
                Posting(partner.code, CREDIT, 2575),
            ],
        )
        db.commit()
        assert account_balance_pence(db, partner) == 1800
        assert account_balance_pence(db, ada) == 0
        assert account_balance_pence(db, bo) == 1800
        debit, credit = assert_ledger_balanced(db)
        assert debit == credit
        rows = db.execute(
            text(
                "SELECT entry_id, "
                "SUM(CASE WHEN direction = 'debit' THEN amount_pence ELSE 0 END), "
                "SUM(CASE WHEN direction = 'credit' THEN amount_pence ELSE 0 END) "
                "FROM ledger_lines GROUP BY entry_id"
            )
        ).all()
        assert rows
        for _entry_id, debit_pence, credit_pence in rows:
            assert int(debit_pence) == int(credit_pence)
            assert int(debit_pence) > 0
    finally:
        db.close()
