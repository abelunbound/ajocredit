"""Append-only double-entry ledger.

Amounts are integer pence. Each entry has two or more lines, and the debit
pence equal the credit pence. Rows are inserted only. A correction is a new
reversing entry, never an update or a delete.

Timestamps come from :func:`clock.now`. Tests move that clock with
``freeze`` and ``advance``. This module does not read the wall clock itself.

The database tables are created by Alembic (``0002_create_ledger``), including
triggers that reject UPDATE and DELETE on SQLite and PostgreSQL.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    event,
    func,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

import clock
from database import Base

DEBIT = "debit"
CREDIT = "credit"
DIRECTIONS = frozenset({DEBIT, CREDIT})
REVERSAL_EXISTS = "entry already has a reversal; post a new entry instead"

ASSET = "asset"
LIABILITY = "liability"
EQUITY = "equity"
INCOME = "income"
EXPENSE = "expense"
KINDS = frozenset({ASSET, LIABILITY, EQUITY, INCOME, EXPENSE})
DEBIT_NORMAL = frozenset({ASSET, EXPENSE})

_MAX_PENCE = 9_223_372_036_854_775_807


class LedgerError(Exception):
    """Base error for ledger writes."""


class LedgerPostingError(LedgerError):
    """A posting breaks double-entry rules or names an unknown account."""


class LedgerAppendOnlyError(LedgerError):
    """An update or delete was attempted on an append-only ledger row."""


class LedgerAccount(Base):
    """A named account in the chart. Codes are permanent."""

    __tablename__ = "ledger_accounts"
    __table_args__ = (
        UniqueConstraint("code", name="uq_ledger_accounts_code"),
        CheckConstraint(
            "kind IN ('asset', 'liability', 'equity', 'income', 'expense')",
            name="ck_ledger_accounts_kind",
        ),
        CheckConstraint("length(currency) = 3", name="ck_ledger_accounts_currency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    circle_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    member_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LedgerEntry(Base):
    """The header of one balanced journal entry."""

    __tablename__ = "ledger_entries"
    __table_args__ = (
        UniqueConstraint("reference", name="uq_ledger_entries_reference"),
        UniqueConstraint("reversal_of_id", name="uq_ledger_entries_reversal_of_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reversal_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("ledger_entries.id", name="fk_ledger_entries_reversal_of_id"),
        nullable=True,
    )

    lines: Mapped[list[LedgerLine]] = relationship(back_populates="entry")


class LedgerLine(Base):
    """One debit or one credit. ``amount_pence`` is a positive integer."""

    __tablename__ = "ledger_lines"
    __table_args__ = (
        CheckConstraint(
            "direction IN ('debit', 'credit')",
            name="ck_ledger_lines_direction",
        ),
        CheckConstraint(
            "amount_pence > 0 AND CAST(amount_pence AS TEXT) NOT LIKE '%.%'",
            name="ck_ledger_lines_amount_positive",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("ledger_entries.id", name="fk_ledger_lines_entry_id"),
        nullable=False,
        index=True,
    )
    account_id: Mapped[int] = mapped_column(
        ForeignKey("ledger_accounts.id", name="fk_ledger_lines_account_id"),
        nullable=False,
        index=True,
    )
    direction: Mapped[str] = mapped_column(String(6), nullable=False)
    amount_pence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    memo: Mapped[str | None] = mapped_column(String(255), nullable=True)

    entry: Mapped[LedgerEntry] = relationship(back_populates="lines")


@dataclass(frozen=True)
class Posting:
    """One side of a journal entry. ``amount_pence`` must be a positive int."""

    account_code: str
    direction: str
    amount_pence: int
    memo: str | None = None


def require_pence(amount: object) -> int:
    """Return ``amount`` when it is a positive integer number of pence."""
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise LedgerPostingError("amount_pence must be an integer number of pence")
    if amount <= 0:
        raise LedgerPostingError("amount_pence must be a positive number of pence")
    if amount > _MAX_PENCE:
        raise LedgerPostingError("amount_pence exceeds the signed 64-bit range")
    return amount


def _clean_text(value: str, field: str, limit: int) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > limit:
        raise LedgerPostingError(f"{field} must be 1..{limit} characters")
    return cleaned


def open_account(
    session: Session,
    *,
    code: str,
    name: str,
    kind: str,
    currency: str = "GBP",
    circle_ref: str | None = None,
    member_ref: str | None = None,
) -> LedgerAccount:
    """Insert an account. Codes are not changed later."""
    code = _clean_text(code, "account code", 128)
    name = _clean_text(name, "account name", 255)
    kind = kind.strip().lower()
    if kind not in KINDS:
        raise LedgerPostingError(f"account kind must be one of: {', '.join(sorted(KINDS))}")
    currency = currency.strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise LedgerPostingError("currency must be a 3-letter code")
    if circle_ref is not None:
        circle_ref = _clean_text(circle_ref, "circle_ref", 64)
    if member_ref is not None:
        member_ref = _clean_text(member_ref, "member_ref", 64)

    existing = session.scalar(select(LedgerAccount.id).where(LedgerAccount.code == code))
    if existing is not None:
        raise LedgerPostingError(f"account already exists: {code}")

    account = LedgerAccount(
        code=code,
        name=name,
        kind=kind,
        currency=currency,
        circle_ref=circle_ref,
        member_ref=member_ref,
        created_at=clock.now(),
    )
    session.add(account)
    try:
        session.flush()
    except IntegrityError as exc:
        raise LedgerPostingError(f"account already exists: {code}") from exc
    return account


def post_entry(
    session: Session,
    *,
    description: str,
    postings: list[Posting] | tuple[Posting, ...],
    reference: str | None = None,
    reversal_of_id: int | None = None,
) -> LedgerEntry:
    """Insert one balanced entry and its lines. Does not commit."""
    description = _clean_text(description, "description", 500)
    if reference is not None:
        reference = _clean_text(reference, "reference", 128)
        taken = session.scalar(select(LedgerEntry.id).where(LedgerEntry.reference == reference))
        if taken is not None:
            raise LedgerPostingError(f"reference already posted: {reference}")
    if len(postings) < 2:
        raise LedgerPostingError("a ledger entry needs at least two lines")

    resolved: list[tuple[LedgerAccount, Posting, int]] = []
    currencies: set[str] = set()
    for posting in postings:
        if posting.direction not in DIRECTIONS:
            raise LedgerPostingError("direction must be debit or credit")
        amount = require_pence(posting.amount_pence)
        if posting.memo is not None and len(posting.memo.strip()) > 255:
            raise LedgerPostingError("memo must be at most 255 characters")
        code = posting.account_code.strip()
        account = session.scalar(select(LedgerAccount).where(LedgerAccount.code == code))
        if account is None:
            raise LedgerPostingError(f"unknown account: {code}")
        currencies.add(account.currency)
        resolved.append((account, posting, amount))
    if len(currencies) != 1:
        raise LedgerPostingError("an entry cannot mix currencies")

    if reversal_of_id is not None:
        original = session.get(LedgerEntry, reversal_of_id)
        if original is None:
            raise LedgerPostingError("reversal target does not exist")

    entry = LedgerEntry(
        posted_at=clock.now(),
        description=description,
        reference=reference,
        reversal_of_id=reversal_of_id,
    )
    session.add(entry)
    for account, posting, amount in resolved:
        memo = posting.memo.strip() if posting.memo else None
        line = LedgerLine(
            account_id=account.id,
            direction=posting.direction,
            amount_pence=amount,
            memo=memo or None,
        )
        entry.lines.append(line)
    try:
        session.flush()
    except IntegrityError as exc:
        if reversal_of_id is not None and _is_reversal_conflict(exc):
            raise LedgerPostingError(REVERSAL_EXISTS) from exc
        raise LedgerPostingError("ledger rejected the entry") from exc

    debit, credit = _stored_entry_totals(session, entry.id)
    if debit != credit or debit <= 0:
        raise LedgerPostingError("debits and credits must balance in pence")
    return entry


def post_reversal(
    session: Session,
    entry_id: int,
    *,
    description: str | None = None,
    reference: str | None = None,
) -> LedgerEntry:
    """Append the opposite entry. The original rows stay as they were."""
    original = session.get(LedgerEntry, entry_id)
    if original is None:
        raise LedgerPostingError("ledger entry does not exist")
    already = session.scalar(
        select(LedgerEntry.id).where(LedgerEntry.reversal_of_id == original.id).limit(1)
    )
    if already is not None:
        raise LedgerPostingError(REVERSAL_EXISTS)

    lines = session.scalars(select(LedgerLine).where(LedgerLine.entry_id == original.id)).all()
    if len(lines) < 2:
        raise LedgerPostingError("original entry has no balanced lines to reverse")

    flipped: list[Posting] = []
    for line in lines:
        account = session.get(LedgerAccount, line.account_id)
        if account is None:
            raise LedgerPostingError("original line is missing its account")
        direction = CREDIT if line.direction == DEBIT else DEBIT
        flipped.append(
            Posting(
                account_code=account.code,
                direction=direction,
                amount_pence=require_pence(line.amount_pence),
                memo=line.memo,
            )
        )
    if description is None:
        description = f"Reversal of entry {original.id}: {original.description}"
        description = description[:500]
    return post_entry(
        session,
        description=description,
        postings=flipped,
        reference=reference,
        reversal_of_id=original.id,
    )


def account_balance_pence(session: Session, account: LedgerAccount) -> int:
    """Signed balance in pence. Assets and expenses are debit-normal."""
    debit, credit = _account_totals(session, account.id)
    if account.kind in DEBIT_NORMAL:
        return debit - credit
    return credit - debit


def format_pence(amount_pence: int, currency: str = "GBP") -> str:
    """Show integer pence as money. ``2575`` and ``GBP`` is ``£25.75``.

    The ledger never stores a float. This divides by 100 only for display.
    """
    if isinstance(amount_pence, bool) or not isinstance(amount_pence, int):
        raise LedgerPostingError("amount_pence must be an integer number of pence")
    sign = "-" if amount_pence < 0 else ""
    pounds, rem = divmod(abs(amount_pence), 100)
    if currency == "GBP":
        return f"{sign}£{pounds}.{rem:02d}"
    return f"{sign}{currency} {pounds}.{rem:02d}"


@dataclass(frozen=True)
class LedgerReadFilters:
    """Read filters. Dates are inclusive bounds on ``posted_at`` in UTC."""

    circle_ref: str | None = None
    member_ref: str | None = None
    account_kind: str | None = None
    posted_from: datetime | None = None
    posted_until: datetime | None = None


@dataclass(frozen=True)
class AccountBalance:
    """Derived figures. Nothing in the database stores these numbers.

    ``balance_pence`` is every entry from the beginning through the end date,
    or through ``clock.now()`` when no end date is set. ``change_in_period_pence``
    is the entries from the start date through that same point. It is ``None``
    when no start date is set.
    """

    account: LedgerAccount
    balance_pence: int
    change_in_period_pence: int | None = None


@dataclass(frozen=True)
class TransactionLine:
    """One side of a transaction, with the account it posted to."""

    line: LedgerLine
    account: LedgerAccount


@dataclass(frozen=True)
class TransactionRecord:
    """One journal entry and every line on it."""

    entry: LedgerEntry
    lines: tuple[TransactionLine, ...]


def _signed_pence(kind: str, direction: str, amount_pence: int) -> int:
    amount = int(amount_pence)
    if kind in DEBIT_NORMAL:
        return amount if direction == DEBIT else -amount
    return amount if direction == CREDIT else -amount


def _accounts_for(session: Session, filters: LedgerReadFilters) -> list[LedgerAccount]:
    stmt = select(LedgerAccount)
    if filters.circle_ref is not None:
        stmt = stmt.where(LedgerAccount.circle_ref == filters.circle_ref)
    if filters.member_ref is not None:
        stmt = stmt.where(LedgerAccount.member_ref == filters.member_ref)
    if filters.account_kind is not None:
        stmt = stmt.where(LedgerAccount.kind == filters.account_kind)
    stmt = stmt.order_by(LedgerAccount.code, LedgerAccount.id)
    return list(session.scalars(stmt).all())


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def query_balances(session: Session, filters: LedgerReadFilters) -> list[AccountBalance]:
    """Derived balance and, when a start date is set, the change in that period.

    Balance is the signed sum of every matching line from the beginning through
    the end of ``posted_until``, or through ``clock.now()`` when no end date
    is set. Change in period is the signed sum from ``posted_from`` through
    that same point. It is omitted when ``posted_from`` is absent. Neither
    figure is stored.
    """
    accounts = _accounts_for(session, filters)
    upper = _as_utc(filters.posted_until) if filters.posted_until is not None else _as_utc(clock.now())
    start = _as_utc(filters.posted_from) if filters.posted_from is not None else None
    totals = {account.id: 0 for account in accounts}
    period = {account.id: 0 for account in accounts} if start is not None else None
    account_ids = [account.id for account in accounts]
    if account_ids:
        rows = session.execute(
            select(LedgerLine, LedgerEntry)
            .join(LedgerEntry, LedgerEntry.id == LedgerLine.entry_id)
            .where(LedgerLine.account_id.in_(account_ids))
            .where(LedgerEntry.posted_at <= upper)
        ).all()
        kinds = {account.id: account.kind for account in accounts}
        for line, entry in rows:
            signed = _signed_pence(kinds[line.account_id], line.direction, int(line.amount_pence))
            totals[line.account_id] += signed
            if period is not None and _as_utc(entry.posted_at) >= start:
                period[line.account_id] += signed
    return [
        AccountBalance(
            account=account,
            balance_pence=totals[account.id],
            change_in_period_pence=None if period is None else period[account.id],
        )
        for account in accounts
    ]


def query_transactions(
    session: Session,
    filters: LedgerReadFilters,
    *,
    page: int,
    page_size: int,
) -> tuple[list[TransactionRecord], int]:
    """Matching journal entries, newest first, with every line on the entry.

    An entry matches when at least one line posts to an account that matches
    the circle, member, and account-type filters, and ``posted_at`` is inside
    the date range. The returned lines include the other side of the entry so
    the transaction still balances on the page.
    """
    if page < 1 or page_size < 1:
        raise LedgerPostingError("page and page_size must be positive")
    accounts = _accounts_for(session, filters)
    account_ids = [account.id for account in accounts]
    if not account_ids:
        return [], 0
    match_ids = (
        select(LedgerEntry.id)
        .join(LedgerLine, LedgerLine.entry_id == LedgerEntry.id)
        .where(LedgerLine.account_id.in_(account_ids))
    )
    if filters.posted_from is not None:
        match_ids = match_ids.where(LedgerEntry.posted_at >= filters.posted_from)
    if filters.posted_until is not None:
        match_ids = match_ids.where(LedgerEntry.posted_at <= filters.posted_until)
    match_ids = match_ids.distinct()
    total = int(session.scalar(select(func.count()).select_from(match_ids.subquery())) or 0)
    id_page = session.scalars(
        select(LedgerEntry.id)
        .where(LedgerEntry.id.in_(match_ids))
        .order_by(LedgerEntry.posted_at.desc(), LedgerEntry.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    if not id_page:
        return [], total
    entries = {
        entry.id: entry
        for entry in session.scalars(select(LedgerEntry).where(LedgerEntry.id.in_(id_page))).all()
    }
    line_rows = session.execute(
        select(LedgerLine, LedgerAccount)
        .join(LedgerAccount, LedgerAccount.id == LedgerLine.account_id)
        .where(LedgerLine.entry_id.in_(id_page))
        .order_by(LedgerLine.entry_id, LedgerLine.id)
    ).all()
    grouped: dict[int, list[TransactionLine]] = {entry_id: [] for entry_id in id_page}
    for line, account in line_rows:
        grouped[line.entry_id].append(TransactionLine(line=line, account=account))
    records = [
        TransactionRecord(entry=entries[entry_id], lines=tuple(grouped[entry_id]))
        for entry_id in id_page
        if entry_id in entries
    ]
    return records, total


def ledger_totals(session: Session) -> tuple[int, int]:
    """Return ``(debit_pence, credit_pence)`` across every line."""
    rows = session.execute(
        select(LedgerLine.direction, LedgerLine.amount_pence)
    ).all()
    debit = 0
    credit = 0
    for direction, amount in rows:
        pence = int(amount)
        if direction == DEBIT:
            debit += pence
        elif direction == CREDIT:
            credit += pence
    return debit, credit


def assert_ledger_balanced(session: Session) -> tuple[int, int]:
    """Raise when total debits and total credits differ."""
    debit, credit = ledger_totals(session)
    if debit != credit:
        raise LedgerPostingError(
            f"ledger is unbalanced: debits {debit} pence, credits {credit} pence"
        )
    return debit, credit


def _account_totals(session: Session, account_id: int) -> tuple[int, int]:
    rows = session.execute(
        select(LedgerLine.direction, LedgerLine.amount_pence).where(
            LedgerLine.account_id == account_id
        )
    ).all()
    debit = 0
    credit = 0
    for direction, amount in rows:
        pence = int(amount)
        if direction == DEBIT:
            debit += pence
        elif direction == CREDIT:
            credit += pence
    return debit, credit


def _stored_entry_totals(session: Session, entry_id: int) -> tuple[int, int]:
    rows = session.execute(
        select(LedgerLine.direction, LedgerLine.amount_pence).where(
            LedgerLine.entry_id == entry_id
        )
    ).all()
    debit = 0
    credit = 0
    for direction, amount in rows:
        pence = int(amount)
        if direction == DEBIT:
            debit += pence
        elif direction == CREDIT:
            credit += pence
    return debit, credit


def _is_reversal_conflict(exc: IntegrityError) -> bool:
    message = str(getattr(exc, "orig", exc)).lower()
    return (
        "uq_ledger_entries_reversal_of_id" in message
        or "ledger_entries.reversal_of_id" in message
    )


def _reject_mutation(_mapper, _connection, _target) -> None:
    raise LedgerAppendOnlyError(
        "the ledger is append-only; corrections are new reversing entries"
    )


for _model in (LedgerAccount, LedgerEntry, LedgerLine):
    event.listens_for(_model, "before_update")(_reject_mutation)
    event.listens_for(_model, "before_delete")(_reject_mutation)


@event.listens_for(Session, "before_flush")
def _guard_ledger_flush(session: Session, _flush_context, _instances) -> None:
    for obj in session.dirty:
        if isinstance(obj, (LedgerAccount, LedgerEntry, LedgerLine)):
            raise LedgerAppendOnlyError(
                "the ledger is append-only; corrections are new reversing entries"
            )
    for obj in session.deleted:
        if isinstance(obj, (LedgerAccount, LedgerEntry, LedgerLine)):
            raise LedgerAppendOnlyError(
                "the ledger is append-only; corrections are new reversing entries"
            )

    new_entries = [obj for obj in session.new if isinstance(obj, LedgerEntry)]
    new_entry_ids = {id(obj) for obj in new_entries}

    for obj in session.new:
        if not isinstance(obj, LedgerLine):
            continue
        entry = obj.entry
        if entry is None or id(entry) not in new_entry_ids:
            raise LedgerAppendOnlyError(
                "ledger lines cannot be added to an existing entry"
            )

    for entry in new_entries:
        _require_balanced_lines(list(entry.lines))


def _require_balanced_lines(lines: list[LedgerLine]) -> None:
    if len(lines) < 2:
        raise LedgerPostingError("a ledger entry needs at least two lines")
    debit = 0
    credit = 0
    for line in lines:
        amount = require_pence(line.amount_pence)
        if line.direction == DEBIT:
            debit += amount
        elif line.direction == CREDIT:
            credit += amount
        else:
            raise LedgerPostingError("direction must be debit or credit")
    if debit != credit or debit == 0:
        raise LedgerPostingError("debits and credits must balance in pence")
