"""Ledger invariant check. Amounts are integer pence.

Two rules, both on posted rows:

1. Every journal entry balances. Debit pence equal credit pence, and the
   entry has at least two lines. A reversal is a posted entry like any other.
   ``reversal_of_id`` does not remove the original from the check.
2. The accounts reconcile: money in = money out + balances.

   * Money in is the signed balances of liability, equity, and income
     (credit-normal: credits − debits).
   * Money out is the signed balances of expense accounts
     (debit-normal: debits − credits).
   * Balances is the signed balances of asset accounts
     (debit-normal: debits − credits).

Both rules have to hold. Two entries can be unbalanced and still cancel
in the totals.

``python -m backend.ledger_balance --seed`` posts a synthetic circle and exits 1
when either rule fails. Seeding runs only when ``AJO_ENV`` is ``local``,
``dev``, or ``ci``. The Postgres CI job sets ``AJO_ENV=ci`` for that command.
A check without ``--seed`` only reads. Nothing here prints a connection
string or a token.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

import backend.database as database
from backend.ledger import (
    ASSET,
    CREDIT,
    DEBIT,
    DEBIT_NORMAL,
    DIRECTIONS,
    EQUITY,
    EXPENSE,
    INCOME,
    KINDS,
    LIABILITY,
    LedgerAccount,
    LedgerEntry,
    LedgerLine,
    LedgerPostingError,
    Posting,
    open_account,
    post_entry,
    post_reversal,
    require_pence,
)

CIRCLE_REF = "circle-synth-ci-balance"
MEMBER_ADA = "member-ada"
MEMBER_BO = "member-bo"

PARTNER_CODE = f"asset:partner:{CIRCLE_REF}"
ADA_CODE = f"liability:{MEMBER_ADA}:{CIRCLE_REF}"
BO_CODE = f"liability:{MEMBER_BO}:{CIRCLE_REF}"
FEE_CODE = f"expense:fee:{CIRCLE_REF}"
INTEREST_CODE = f"income:interest:{CIRCLE_REF}"
EQUITY_CODE = f"equity:opening:{CIRCLE_REF}"

EQUITY_PENCE = 1000
ADA_CONTRIBUTION_PENCE = 2575
BO_CONTRIBUTION_PENCE = 5000
FEE_PENCE = 75
INTEREST_PENCE = 25
MISTAKE_PENCE = 100

REF_EQUITY = "ci-balance-equity"
REF_ADA = "ci-balance-ada-in"
REF_BO = "ci-balance-bo-in"
REF_FEE = "ci-balance-fee"
REF_INTEREST = "ci-balance-interest"
REF_MISTAKE = "ci-balance-ada-mistake"
REF_MISTAKE_REVERSAL = "ci-balance-ada-mistake-reversal"

# Seeding writes rows. These are the only environments that may do that.
SEED_ENVS = frozenset({"local", "dev", "ci"})


class LedgerInvariantError(Exception):
    """Posted rows break a ledger invariant."""

    def __init__(self, result: "LedgerInvariantResult"):
        self.result = result
        detail = "\n".join(result.problems) or "ledger balance mismatch"
        super().__init__(detail)


@dataclass(frozen=True)
class PostedLine:
    """One stored side of a journal entry, in integer pence."""

    entry_id: int
    account_kind: str
    direction: str
    amount_pence: object
    currency: str


@dataclass(frozen=True)
class LedgerInvariantResult:
    """Outcome of one check. Figures are integer pence."""

    ok: bool
    money_in_pence: int
    money_out_pence: int
    balances_pence: int
    problems: tuple[str, ...]


def check_posted_lines(
    lines: Sequence[PostedLine],
    entry_ids: Sequence[int] = (),
) -> LedgerInvariantResult:
    """Check transactions and the money-in equation. Does not touch the database."""
    grouped: dict[int, list[PostedLine]] = {}
    for entry_id in entry_ids:
        grouped.setdefault(int(entry_id), [])
    for line in lines:
        grouped.setdefault(int(line.entry_id), []).append(line)

    problems: list[str] = []
    for entry_id in sorted(grouped):
        problems.extend(_entry_problems(entry_id, grouped[entry_id]))

    debit_by_kind = {kind: 0 for kind in KINDS}
    credit_by_kind = {kind: 0 for kind in KINDS}
    currencies: set[str] = set()
    for line in lines:
        amount = _usable_amount(line)
        if amount is None:
            continue
        currencies.add(line.currency)
        if line.direction == DEBIT:
            debit_by_kind[line.account_kind] += amount
        else:
            credit_by_kind[line.account_kind] += amount

    def _balance(kind: str) -> int:
        if kind in DEBIT_NORMAL:
            return debit_by_kind[kind] - credit_by_kind[kind]
        return credit_by_kind[kind] - debit_by_kind[kind]

    money_in = _balance(LIABILITY) + _balance(EQUITY) + _balance(INCOME)
    money_out = _balance(EXPENSE)
    balances = _balance(ASSET)

    if len(currencies) > 1:
        listed = ", ".join(sorted(currencies))
        problems.append(f"ledger lines use more than one currency: {listed}")
    if money_in != money_out + balances:
        problems.append(
            "ledger does not reconcile: "
            f"money_in {money_in} pence != money_out {money_out} pence + balances {balances} pence"
        )

    return LedgerInvariantResult(
        ok=not problems,
        money_in_pence=money_in,
        money_out_pence=money_out,
        balances_pence=balances,
        problems=tuple(problems),
    )


def check_ledger_invariants(session: Session) -> LedgerInvariantResult:
    """Check every posted entry and the sum across all accounts."""
    rows = session.execute(
        select(
            LedgerEntry.id,
            LedgerLine.direction,
            LedgerLine.amount_pence,
            LedgerAccount.kind,
            LedgerAccount.currency,
        )
        .select_from(LedgerEntry)
        .outerjoin(LedgerLine, LedgerLine.entry_id == LedgerEntry.id)
        .outerjoin(LedgerAccount, LedgerAccount.id == LedgerLine.account_id)
        .order_by(LedgerEntry.id, LedgerLine.id)
    ).all()

    entry_ids: list[int] = []
    lines: list[PostedLine] = []
    seen: set[int] = set()
    for entry_id, direction, amount, kind, currency in rows:
        entry_key = int(entry_id)
        if entry_key not in seen:
            seen.add(entry_key)
            entry_ids.append(entry_key)
        if direction is None:
            continue
        lines.append(
            PostedLine(
                entry_id=entry_key,
                account_kind="" if kind is None else str(kind),
                direction=str(direction),
                amount_pence=amount,
                currency="" if currency is None else str(currency),
            )
        )
    return check_posted_lines(lines, entry_ids)


def require_ledger_invariants(session: Session) -> LedgerInvariantResult:
    """Return the check result, or raise when a posted row breaks a rule."""
    result = check_ledger_invariants(session)
    if not result.ok:
        raise LedgerInvariantError(result)
    return result


def seed_synthetic_ledger(session: Session) -> None:
    """Post the synthetic CI circle. A second call does not post it again.

    Refs are ``circle-synth-ci-balance``, ``member-ada``, and ``member-bo``.
    There is no email address and no bank detail. ``posted_at`` comes from
    ``clock.now()`` inside ``post_entry``. The mistaken contribution is
    corrected by ``post_reversal``, which sets ``reversal_of_id``.
    """
    partner = _open(
        session,
        code=PARTNER_CODE,
        name="Synthetic partner clearing",
        kind=ASSET,
        circle_ref=CIRCLE_REF,
    )
    ada = _open(
        session,
        code=ADA_CODE,
        name="Synthetic member Ada contributions",
        kind=LIABILITY,
        circle_ref=CIRCLE_REF,
        member_ref=MEMBER_ADA,
    )
    bo = _open(
        session,
        code=BO_CODE,
        name="Synthetic member Bo contributions",
        kind=LIABILITY,
        circle_ref=CIRCLE_REF,
        member_ref=MEMBER_BO,
    )
    fee = _open(
        session,
        code=FEE_CODE,
        name="Synthetic circle fee",
        kind=EXPENSE,
        circle_ref=CIRCLE_REF,
    )
    interest = _open(
        session,
        code=INTEREST_CODE,
        name="Synthetic circle interest",
        kind=INCOME,
        circle_ref=CIRCLE_REF,
    )
    equity = _open(
        session,
        code=EQUITY_CODE,
        name="Synthetic opening equity",
        kind=EQUITY,
        circle_ref=CIRCLE_REF,
    )
    _post(
        session,
        REF_EQUITY,
        "Synthetic equity opening",
        [Posting(partner.code, DEBIT, EQUITY_PENCE), Posting(equity.code, CREDIT, EQUITY_PENCE)],
    )
    _post(
        session,
        REF_ADA,
        "Synthetic Ada contribution",
        [
            Posting(partner.code, DEBIT, ADA_CONTRIBUTION_PENCE),
            Posting(ada.code, CREDIT, ADA_CONTRIBUTION_PENCE),
        ],
    )
    _post(
        session,
        REF_BO,
        "Synthetic Bo contribution",
        [
            Posting(partner.code, DEBIT, BO_CONTRIBUTION_PENCE),
            Posting(bo.code, CREDIT, BO_CONTRIBUTION_PENCE),
        ],
    )
    _post(
        session,
        REF_FEE,
        "Synthetic circle fee",
        [Posting(fee.code, DEBIT, FEE_PENCE), Posting(partner.code, CREDIT, FEE_PENCE)],
    )
    _post(
        session,
        REF_INTEREST,
        "Synthetic circle interest",
        [
            Posting(partner.code, DEBIT, INTEREST_PENCE),
            Posting(interest.code, CREDIT, INTEREST_PENCE),
        ],
    )
    mistake_id = _post(
        session,
        REF_MISTAKE,
        "Synthetic Ada contribution posted by mistake",
        [
            Posting(partner.code, DEBIT, MISTAKE_PENCE),
            Posting(ada.code, CREDIT, MISTAKE_PENCE),
        ],
    )
    _reverse_once(session, mistake_id, REF_MISTAKE_REVERSAL)


def seed_refusal(source: Mapping[str, str] | None = None) -> str | None:
    """Why ``--seed`` must stop, or None when ``AJO_ENV`` is local, dev, or ci.

    Comparison ignores case and surrounding space. An unset or blank value
    is refused. Any other value is refused.
    """
    env = os.environ if source is None else source
    raw = env.get("AJO_ENV")
    cleaned = "" if raw is None else str(raw).strip().lower()
    if cleaned in SEED_ENVS:
        return None
    shown = "(unset)" if raw is None or str(raw).strip() == "" else str(raw).strip()
    return (
        f"AJO_ENV is {shown!r}; refusing to seed the synthetic ledger. "
        "Seeding is allowed only when AJO_ENV is local, dev, or ci."
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Seed when asked, then check. Return 1 when the ledger does not balance.

    ``--seed`` returns 1 before opening the database when ``AJO_ENV`` is not
    local, dev, or ci. A run without ``--seed`` only reads, in any environment.
    """
    parser = argparse.ArgumentParser(description="Check ledger invariants in integer pence.")
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Post the synthetic ledger. Allowed only when AJO_ENV is local, dev, or ci.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.seed:
        refusal = seed_refusal()
        if refusal is not None:
            print(refusal, file=sys.stderr)
            return 1
    session = database.SessionLocal()
    try:
        if args.seed:
            seed_synthetic_ledger(session)
            session.commit()
        result = check_ledger_invariants(session)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    if result.ok:
        print(
            "ledger balances: "
            f"money_in={result.money_in_pence} "
            f"money_out={result.money_out_pence} "
            f"balances={result.balances_pence}"
        )
        return 0
    for problem in result.problems:
        print(problem, file=sys.stderr)
    return 1


def _entry_problems(entry_id: int, entry_lines: Sequence[PostedLine]) -> list[str]:
    if len(entry_lines) < 2:
        return [
            f"entry {entry_id} does not balance: a posted transaction needs at least two lines"
        ]
    problems: list[str] = []
    debit = 0
    credit = 0
    for line in entry_lines:
        if line.direction not in DIRECTIONS:
            problems.append(
                f"entry {entry_id} does not balance: line direction is not debit or credit"
            )
            continue
        amount = _usable_amount(line)
        if amount is None:
            if line.account_kind not in KINDS:
                problems.append(f"entry {entry_id} does not balance: account kind is unknown")
            elif not _currency_ok(line.currency):
                problems.append(
                    f"entry {entry_id} does not balance: currency is not a 3-letter code"
                )
            else:
                problems.append(
                    f"entry {entry_id} does not balance: amount_pence is not a positive integer"
                )
            continue
        if line.direction == DEBIT:
            debit += amount
        else:
            credit += amount
    if problems:
        return problems
    if debit != credit or debit <= 0:
        return [
            f"entry {entry_id} does not balance: debits {debit} pence, credits {credit} pence"
        ]
    return []


def _usable_amount(line: PostedLine) -> int | None:
    """Integer pence to include in a sum, or None when the line cannot be summed."""
    if line.direction not in DIRECTIONS or line.account_kind not in KINDS:
        return None
    if not _currency_ok(line.currency):
        return None
    try:
        return require_pence(line.amount_pence)
    except LedgerPostingError:
        return None


def _currency_ok(currency: object) -> bool:
    return isinstance(currency, str) and len(currency) == 3 and currency.isalpha()


def _open(session: Session, **kwargs: object) -> LedgerAccount:
    code = str(kwargs["code"])
    existing = session.scalar(select(LedgerAccount).where(LedgerAccount.code == code))
    if existing is not None:
        return existing
    return open_account(session, **kwargs)  # type: ignore[arg-type]


def _post(
    session: Session,
    reference: str,
    description: str,
    postings: list[Posting],
) -> int:
    existing = session.scalar(select(LedgerEntry.id).where(LedgerEntry.reference == reference))
    if existing is not None:
        return int(existing)
    entry = post_entry(
        session,
        description=description,
        reference=reference,
        postings=postings,
    )
    return int(entry.id)


def _reverse_once(session: Session, entry_id: int, reference: str) -> None:
    existing = session.scalar(select(LedgerEntry.id).where(LedgerEntry.reference == reference))
    if existing is not None:
        return
    post_reversal(session, entry_id, reference=reference)


if __name__ == "__main__":
    raise SystemExit(main())
