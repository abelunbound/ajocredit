"""Ledger invariant check: every entry balances, and money in = money out + balances.

Synthetic refs only. A mismatch is inserted with SQL and rolled back. The
application would have rejected it; the checker still has to fail.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

import pytest

_configured_url = os.environ.get("DATABASE_URL", "")
USING_POSTGRES = _configured_url.startswith("postgres")
if not USING_POSTGRES and not _configured_url.startswith("sqlite"):
    _db_dir = tempfile.mkdtemp(prefix="ajo-ledger-balance-")
    os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_db_dir) / "ajo.db")

from alembic import command
from alembic.config import Config
from sqlalchemy import insert, select

import clock
import database
import ledger_balance
from ledger import (
    ASSET,
    CREDIT,
    DEBIT,
    EQUITY,
    EXPENSE,
    INCOME,
    LIABILITY,
    LedgerAccount,
    LedgerEntry,
    LedgerLine,
    account_balance_pence,
)
from ledger_balance import (
    ADA_CODE,
    ADA_CONTRIBUTION_PENCE,
    BO_CODE,
    BO_CONTRIBUTION_PENCE,
    EQUITY_CODE,
    EQUITY_PENCE,
    FEE_CODE,
    FEE_PENCE,
    INTEREST_CODE,
    INTEREST_PENCE,
    MISTAKE_PENCE,
    PARTNER_CODE,
    REF_MISTAKE,
    REF_MISTAKE_REVERSAL,
    LedgerInvariantError,
    PostedLine,
    check_posted_lines,
    main,
    require_ledger_invariants,
    seed_synthetic_ledger,
)

_ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
command.upgrade(Config(str(_ALEMBIC_INI)), "head")


def setup_function() -> None:
    clock.restore_for_tests()


def teardown_function() -> None:
    clock.restore_for_tests()


def _session():
    return database.SessionLocal()


def _seeded():
    db = _session()
    seed_synthetic_ledger(db)
    db.commit()
    return db


def _account_id(db, code: str) -> int:
    account_id = db.scalar(select(LedgerAccount.id).where(LedgerAccount.code == code))
    assert account_id is not None
    return int(account_id)


def _insert_raw_entry(db, lines: list[tuple[int, str, int]]) -> int:
    """Store lines the posting API would reject. The balance triggers allow INSERT."""
    reference = f"ci-balance-broken-{uuid.uuid4().hex}"
    entry_id = db.execute(
        insert(LedgerEntry)
        .values(
            posted_at=clock.now(),
            description="Broken synthetic fixture",
            reference=reference,
        )
        .returning(LedgerEntry.id)
    ).scalar_one()
    for account_id, direction, amount in lines:
        db.execute(
            insert(LedgerLine).values(
                entry_id=entry_id,
                account_id=account_id,
                direction=direction,
                amount_pence=amount,
            )
        )
    return int(entry_id)


def _seed_lines() -> list[PostedLine]:
    """The CI seed as lines, including the mistake and its reversal."""

    def pair(entry_id: int, debit_kind: str, credit_kind: str, amount: int) -> list[PostedLine]:
        return [
            PostedLine(entry_id, debit_kind, DEBIT, amount, "GBP"),
            PostedLine(entry_id, credit_kind, CREDIT, amount, "GBP"),
        ]

    lines: list[PostedLine] = []
    lines += pair(1, ASSET, EQUITY, EQUITY_PENCE)
    lines += pair(2, ASSET, LIABILITY, ADA_CONTRIBUTION_PENCE)
    lines += pair(3, ASSET, LIABILITY, BO_CONTRIBUTION_PENCE)
    lines += pair(4, EXPENSE, ASSET, FEE_PENCE)
    lines += pair(5, ASSET, INCOME, INTEREST_PENCE)
    lines += pair(6, ASSET, LIABILITY, MISTAKE_PENCE)
    lines += pair(7, LIABILITY, ASSET, MISTAKE_PENCE)
    return lines


def test_seed_shaped_lines_reconcile_in_pence():
    result = check_posted_lines(_seed_lines())
    assert result.ok
    assert result.problems == ()
    assert result.money_in_pence == 8600
    assert result.money_out_pence == 75
    assert result.balances_pence == 8525
    assert result.money_in_pence == result.money_out_pence + result.balances_pence


def test_empty_ledger_reconciles_at_zero():
    result = check_posted_lines(())
    assert result.ok
    assert (result.money_in_pence, result.money_out_pence, result.balances_pence) == (0, 0, 0)


def test_one_unbalanced_entry_breaks_the_equation():
    result = check_posted_lines(
        [
            PostedLine(1, ASSET, DEBIT, 1000, "GBP"),
            PostedLine(1, LIABILITY, CREDIT, 900, "GBP"),
        ]
    )
    assert result.ok is False
    assert result.problems == (
        "entry 1 does not balance: debits 1000 pence, credits 900 pence",
        "ledger does not reconcile: money_in 900 pence != money_out 0 pence + balances 1000 pence",
    )


def test_offsetting_unbalanced_entries_still_fail_when_the_totals_cancel():
    """Total debits can equal total credits while each transaction is wrong."""
    result = check_posted_lines(
        [
            PostedLine(1, ASSET, DEBIT, 1000, "GBP"),
            PostedLine(1, LIABILITY, CREDIT, 900, "GBP"),
            PostedLine(2, ASSET, DEBIT, 900, "GBP"),
            PostedLine(2, LIABILITY, CREDIT, 1000, "GBP"),
        ]
    )
    assert result.ok is False
    assert result.money_in_pence == result.money_out_pence + result.balances_pence
    assert result.problems == (
        "entry 1 does not balance: debits 1000 pence, credits 900 pence",
        "entry 2 does not balance: debits 900 pence, credits 1000 pence",
    )


def test_header_without_lines_fails_and_the_equation_stays_zero():
    result = check_posted_lines((), entry_ids=(4,))
    assert result.ok is False
    assert result.money_in_pence == result.money_out_pence + result.balances_pence
    assert result.problems == (
        "entry 4 does not balance: a posted transaction needs at least two lines",
    )


def test_mixed_currencies_fail():
    result = check_posted_lines(
        [
            PostedLine(1, ASSET, DEBIT, 100, "GBP"),
            PostedLine(1, LIABILITY, CREDIT, 100, "USD"),
        ]
    )
    assert result.ok is False
    assert "ledger lines use more than one currency: GBP, USD" in result.problems


def test_seeded_synthetic_ledger_reconciles_and_keeps_the_reversal():
    db = _seeded()
    try:
        seed_synthetic_ledger(db)
        db.commit()
        expected = {
            PARTNER_CODE: 8525,
            ADA_CODE: 2575,
            BO_CODE: 5000,
            FEE_CODE: 75,
            INTEREST_CODE: 25,
            EQUITY_CODE: 1000,
        }
        for code, balance in expected.items():
            account = db.scalar(select(LedgerAccount).where(LedgerAccount.code == code))
            assert account is not None
            assert account_balance_pence(db, account) == balance
            assert isinstance(account_balance_pence(db, account), int)
        original = db.scalar(select(LedgerEntry).where(LedgerEntry.reference == REF_MISTAKE))
        reversal = db.scalar(
            select(LedgerEntry).where(LedgerEntry.reference == REF_MISTAKE_REVERSAL)
        )
        assert original is not None and reversal is not None
        assert reversal.reversal_of_id == original.id
        result = require_ledger_invariants(db)
        assert result.money_in_pence == result.money_out_pence + result.balances_pence
    finally:
        db.close()


def test_injected_unbalanced_entry_fails_the_checker_and_rolls_back():
    db = _seeded()
    try:
        partner_id = _account_id(db, PARTNER_CODE)
        ada_id = _account_id(db, ADA_CODE)
        entry_id = _insert_raw_entry(db, [(partner_id, DEBIT, 1000), (ada_id, CREDIT, 900)])
        with pytest.raises(LedgerInvariantError) as caught:
            require_ledger_invariants(db)
        message = str(caught.value)
        assert f"entry {entry_id} does not balance: debits 1000 pence, credits 900 pence" in message
        assert "ledger does not reconcile:" in message
        assert caught.value.result.ok is False
        assert (
            caught.value.result.money_in_pence
            != caught.value.result.money_out_pence + caught.value.result.balances_pence
        )
        db.rollback()
        require_ledger_invariants(db)
    finally:
        db.rollback()
        db.close()


def test_injected_header_without_lines_fails_the_checker():
    db = _seeded()
    try:
        entry_id = _insert_raw_entry(db, [])
        with pytest.raises(LedgerInvariantError) as caught:
            require_ledger_invariants(db)
        assert (
            f"entry {entry_id} does not balance: a posted transaction needs at least two lines"
            in str(caught.value)
        )
        db.rollback()
        require_ledger_invariants(db)
    finally:
        db.rollback()
        db.close()


def test_injected_offsetting_mismatch_fails_even_though_the_books_still_sum():
    db = _seeded()
    try:
        partner_id = _account_id(db, PARTNER_CODE)
        ada_id = _account_id(db, ADA_CODE)
        first = _insert_raw_entry(db, [(partner_id, DEBIT, 1000), (ada_id, CREDIT, 900)])
        second = _insert_raw_entry(db, [(partner_id, DEBIT, 900), (ada_id, CREDIT, 1000)])
        with pytest.raises(LedgerInvariantError) as caught:
            require_ledger_invariants(db)
        message = str(caught.value)
        assert f"entry {first} does not balance: debits 1000 pence, credits 900 pence" in message
        assert f"entry {second} does not balance: debits 900 pence, credits 1000 pence" in message
        assert "ledger does not reconcile:" not in message
        assert (
            caught.value.result.money_in_pence
            == caught.value.result.money_out_pence + caught.value.result.balances_pence
        )
        db.rollback()
        require_ledger_invariants(db)
    finally:
        db.rollback()
        db.close()


def test_cli_seed_exits_zero_when_the_ledger_balances(monkeypatch, capsys):
    monkeypatch.setenv("AJO_ENV", "ci")
    assert main(["--seed"]) == 0
    out = capsys.readouterr().out
    assert "://" not in out
    assert out.startswith("ledger balances: ")
    parts = {}
    for token in out.split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        parts[key] = int(value)
    assert parts["money_in"] == parts["money_out"] + parts["balances"]


@pytest.mark.parametrize("env_name", ["local", "dev", "ci", "CI", "Local", "  Dev  "])
def test_seed_runs_for_local_dev_or_ci(monkeypatch, capsys, env_name):
    monkeypatch.setenv("AJO_ENV", env_name)
    assert main(["--seed"]) == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("ledger balances: ")
    assert "refusing to seed" not in captured.err
    assert "://" not in captured.out


@pytest.mark.parametrize(
    "env_name",
    [None, "", "   ", "production", "staging", "test", "prod", "localdev"],
)
def test_seed_refuses_for_any_other_ajo_env(monkeypatch, capsys, env_name):
    if env_name is None:
        monkeypatch.delenv("AJO_ENV", raising=False)
    else:
        monkeypatch.setenv("AJO_ENV", env_name)

    def _opened():
        raise AssertionError("database opened")

    monkeypatch.setattr(ledger_balance.database, "SessionLocal", _opened)
    assert main(["--seed"]) == 1
    err = capsys.readouterr().err
    assert "refusing to seed the synthetic ledger" in err
    assert "local, dev, or ci" in err
    assert "://" not in err
    if env_name is None or env_name.strip() == "":
        assert "AJO_ENV is '(unset)'" in err
    else:
        assert f"AJO_ENV is {env_name.strip()!r}" in err


@pytest.mark.parametrize("env_name", [None, "", "production", "staging"])
def test_readonly_check_runs_when_seeding_is_refused(monkeypatch, capsys, env_name):
    if env_name is None:
        monkeypatch.delenv("AJO_ENV", raising=False)
    else:
        monkeypatch.setenv("AJO_ENV", env_name)
    assert main([]) == 0
    captured = capsys.readouterr()
    assert captured.out.startswith("ledger balances: ")
    assert "refusing to seed" not in captured.err


def test_cli_exits_nonzero_when_the_checker_reports_a_mismatch(monkeypatch, capsys):
    broken = check_posted_lines(
        [
            PostedLine(1, ASSET, DEBIT, 1000, "GBP"),
            PostedLine(1, LIABILITY, CREDIT, 900, "GBP"),
        ]
    )
    assert broken.ok is False

    def _broken(_session):
        return broken

    monkeypatch.setattr("ledger_balance.check_ledger_invariants", _broken)
    assert main([]) == 1
    captured = capsys.readouterr()
    assert "entry 1 does not balance: debits 1000 pence, credits 900 pence" in captured.err
    assert "ledger does not reconcile:" in captured.err
    assert "://" not in captured.err
    assert "://" not in captured.out
