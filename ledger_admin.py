"""Read-only platform-admin view of the ledger.

Balances are summed from lines at read time. The page and the API only
register GET routes. Access uses :func:`audit.is_platform_admin`, which reads
``users.platform_role``. A circle admin is not a platform admin. Query
strings, headers, and body fields are not a role.

A successful read calls :func:`audit.record_event` with action
``financial_data_viewed``. The time is ``clock.now()``. This module does not
update or delete ledger rows.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

import clock
from audit import PLATFORM_ADMIN, is_platform_admin, record_event
from database import User, get_db
from ledger import (
    KINDS,
    AccountBalance,
    LedgerReadFilters,
    TransactionRecord,
    format_pence,
    query_balances,
    query_transactions,
)

NOT_ALLOWED = "Not allowed."
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 50
_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")
VIEW_ACTION = "financial_data_viewed"


@dataclass(frozen=True)
class PageQuery:
    filters: LedgerReadFilters
    circle_raw: str
    member_raw: str
    account_type_raw: str
    start_raw: str
    end_raw: str
    page: int
    page_size: int


def _clean_ref(value: str, field: str) -> str | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > 64:
        raise HTTPException(status_code=422, detail=f"{field} must be at most 64 characters.")
    return cleaned


def _parse_day(value: str, field: str) -> datetime | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    if not _DAY.fullmatch(cleaned):
        raise HTTPException(status_code=422, detail=f"{field} must be YYYY-MM-DD.")
    try:
        return datetime.strptime(cleaned, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"{field} must be YYYY-MM-DD.") from exc


def _parse_positive(value: str, field: str, *, default: int, maximum: int) -> int:
    cleaned = value.strip()
    if not cleaned:
        return default
    if not cleaned.isdigit():
        raise HTTPException(status_code=422, detail=f"{field} must be a positive integer.")
    number = int(cleaned)
    if number < 1 or number > maximum:
        raise HTTPException(
            status_code=422,
            detail=f"{field} must be from 1 to {maximum}.",
        )
    return number


def parse_query(params) -> PageQuery:
    """Read filters. Unknown params, including a client role, are ignored."""
    circle_raw = str(params.get("circle") or "")
    member_raw = str(params.get("member") or "")
    account_type_raw = str(params.get("account_type") or "")
    start_raw = str(params.get("start") or "")
    end_raw = str(params.get("end") or "")
    circle = _clean_ref(circle_raw, "circle")
    member = _clean_ref(member_raw, "member")
    kind_text = account_type_raw.strip().lower()
    kind = None
    if kind_text:
        if kind_text not in KINDS:
            raise HTTPException(
                status_code=422,
                detail="account_type must be asset, liability, equity, income, or expense.",
            )
        kind = kind_text
    start = _parse_day(start_raw, "start")
    end_day = _parse_day(end_raw, "end")
    if start is not None and end_day is not None and end_day < start:
        raise HTTPException(status_code=422, detail="end must be on or after start.")
    # Inclusive calendar day, compared with timezone-aware UTC timestamps.
    posted_until = None if end_day is None else end_day + timedelta(days=1) - timedelta(microseconds=1)
    page = _parse_positive(str(params.get("page") or ""), "page", default=1, maximum=1_000_000)
    page_size = _parse_positive(
        str(params.get("page_size") or ""),
        "page_size",
        default=DEFAULT_PAGE_SIZE,
        maximum=MAX_PAGE_SIZE,
    )
    return PageQuery(
        filters=LedgerReadFilters(
            circle_ref=circle,
            member_ref=member,
            account_kind=kind,
            posted_from=start,
            posted_until=posted_until,
        ),
        circle_raw=circle or "",
        member_raw=member or "",
        account_type_raw=kind or "",
        start_raw=start_raw.strip(),
        end_raw=end_raw.strip(),
        page=page,
        page_size=page_size,
    )


def record_ledger_view(db: Session, request: Request, user: User, query: PageQuery) -> None:
    """Append ``financial_data_viewed`` on the audit log. Does not commit.

    No email address is passed. ``after`` holds the filters.
    """
    record_event(
        db,
        action=VIEW_ACTION,
        actor_user_id=user.id,
        actor_role=PLATFORM_ADMIN,
        request=request,
        at=clock.now(),
        after={
            "view": "ledger",
            "circle": query.filters.circle_ref,
            "member": query.filters.member_ref,
            "account_type": query.filters.account_kind,
            "start": query.start_raw or None,
            "end": query.end_raw or None,
            "page": query.page,
            "page_size": query.page_size,
            "allowed": True,
        },
    )


def _balance_payload(row: AccountBalance) -> dict:
    account = row.account
    payload = {
        "account_id": account.id,
        "code": account.code,
        "name": account.name,
        "account_type": account.kind,
        "currency": account.currency,
        "circle": account.circle_ref,
        "member": account.member_ref,
        "balance_pence": int(row.balance_pence),
        "balance_display": format_pence(int(row.balance_pence), account.currency),
    }
    if row.change_in_period_pence is not None:
        payload["change_in_period_pence"] = int(row.change_in_period_pence)
        payload["change_in_period_display"] = format_pence(
            int(row.change_in_period_pence), account.currency
        )
    return payload


def _transaction_payload(record: TransactionRecord) -> dict:
    entry = record.entry
    return {
        "id": entry.id,
        "posted_at": entry.posted_at.isoformat(),
        "description": entry.description,
        "reference": entry.reference,
        "reversal_of_id": entry.reversal_of_id,
        "entries": [
            {
                "id": line.line.id,
                "account_id": line.account.id,
                "account_code": line.account.code,
                "account_type": line.account.kind,
                "circle": line.account.circle_ref,
                "member": line.account.member_ref,
                "direction": line.line.direction,
                "amount_pence": int(line.line.amount_pence),
                "amount_display": format_pence(int(line.line.amount_pence), line.account.currency),
                "memo": line.line.memo,
            }
            for line in record.lines
        ],
    }


def load_ledger(db: Session, request: Request, user: User) -> tuple[PageQuery, list[AccountBalance], list[TransactionRecord], int]:
    """Authorise, read, and audit. Ledger rows are not modified."""
    if not is_platform_admin(user):
        raise HTTPException(status_code=403, detail=NOT_ALLOWED)
    query = parse_query(request.query_params)
    balances = query_balances(db, query.filters)
    transactions, total = query_transactions(
        db, query.filters, page=query.page, page_size=query.page_size
    )
    record_ledger_view(db, request, user, query)
    db.commit()
    return query, balances, transactions, total


def _cell(value: object) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _render_page(
    query: PageQuery,
    balances: list[AccountBalance],
    transactions: list[TransactionRecord],
    total: int,
) -> str:
    show_change = query.filters.posted_from is not None
    balance_rows = []
    for row in balances:
        account = row.account
        change_cells = ""
        if show_change:
            change_pence = int(row.change_in_period_pence or 0)
            change_cells = (
                f"<td>{change_pence}</td>"
                f"<td>{_cell(format_pence(change_pence, account.currency))}</td>"
            )
        balance_rows.append(
            "<tr>"
            f"<td>{_cell(account.code)}</td>"
            f"<td>{_cell(account.name)}</td>"
            f"<td>{_cell(account.kind)}</td>"
            f"<td>{_cell(account.circle_ref)}</td>"
            f"<td>{_cell(account.member_ref)}</td>"
            f"<td>{int(row.balance_pence)}</td>"
            f"<td>{_cell(format_pence(int(row.balance_pence), account.currency))}</td>"
            f"{change_cells}"
            "</tr>"
        )
    balance_span = "9" if show_change else "7"
    if not balance_rows:
        balance_rows.append(f'<tr><td colspan="{balance_span}">No accounts.</td></tr>')
    change_headers = ""
    if show_change:
        change_headers = "<th>Change in period (pence)</th><th>Change in period</th>"

    entry_rows = []
    for record in transactions:
        entry = record.entry
        posted = entry.posted_at.isoformat()
        for line in record.lines:
            entry_rows.append(
                "<tr>"
                f"<td>{_cell(posted)}</td>"
                f"<td>{entry.id}</td>"
                f"<td>{_cell(entry.description)}</td>"
                f"<td>{_cell(entry.reference)}</td>"
                f"<td>{_cell(entry.reversal_of_id)}</td>"
                f"<td>{_cell(line.account.code)}</td>"
                f"<td>{_cell(line.account.kind)}</td>"
                f"<td>{_cell(line.line.direction)}</td>"
                f"<td>{int(line.line.amount_pence)}</td>"
                f"<td>{_cell(format_pence(int(line.line.amount_pence), line.account.currency))}</td>"
                f"<td>{_cell(line.line.memo)}</td>"
                "</tr>"
            )
    if not entry_rows:
        entry_rows.append('<tr><td colspan="11">No transactions.</td></tr>')

    pages = max(1, (total + query.page_size - 1) // query.page_size)

    def page_href(page: int) -> str:
        pairs = {
            "circle": query.circle_raw,
            "member": query.member_raw,
            "account_type": query.account_type_raw,
            "start": query.start_raw,
            "end": query.end_raw,
            "page": str(page),
            "page_size": str(query.page_size),
        }
        return "/admin/ledger?" + "&".join(
            f"{html.escape(key, quote=True)}={html.escape(value, quote=True)}"
            for key, value in pairs.items()
        )

    prev_link = ""
    next_link = ""
    if query.page > 1:
        prev_link = f'<a href="{page_href(query.page - 1)}">Previous</a>'
    if query.page < pages:
        next_link = f'<a href="{page_href(query.page + 1)}">Next</a>'
    options = ['<option value="">All</option>']
    for kind in sorted(KINDS):
        selected = " selected" if kind == query.account_type_raw else ""
        options.append(f'<option value="{kind}"{selected}>{kind}</option>')
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ledger</title>
<style>
body {{ font-family: Georgia, "Times New Roman", serif; margin: 2rem; color: #1c1915; background: #f7f4ee; }}
h1, h2 {{ font-weight: normal; }}
form {{ display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: end; margin: 1rem 0 1.5rem; }}
label {{ display: flex; flex-direction: column; font-size: 0.85rem; gap: 0.25rem; }}
input, select {{ font: inherit; padding: 0.35rem 0.5rem; border: 1px solid #c9c1b4; background: #fff; }}
button {{ font: inherit; padding: 0.4rem 0.8rem; background: #1c1915; color: #f7f4ee; border: 0; }}
table {{ width: 100%; border-collapse: collapse; background: #fff; margin-bottom: 2rem; }}
th, td {{ text-align: left; padding: 0.45rem 0.55rem; border-bottom: 1px solid #e4ddd2; font-size: 0.9rem; }}
.note {{ color: #5c564c; max-width: 46rem; }}
.pager {{ display: flex; gap: 1rem; margin-top: 1rem; }}
</style>
</head>
<body>
<h1>Ledger</h1>
<p class="note">Read-only. Amounts are integer pence and are calculated from entries, not stored. Balance is every entry from the beginning up to the end date, or up to now when no end date is set. Change in period is the entries inside the date range and is shown only when a start date is set. This page cannot create, edit, or delete anything. Opening it is audit-logged.</p>
<form method="get" action="/admin/ledger">
<label>Circle<input name="circle" value="{_cell(query.circle_raw)}"></label>
<label>Member<input name="member" value="{_cell(query.member_raw)}"></label>
<label>Account type<select name="account_type">{"".join(options)}</select></label>
<label>Start<input name="start" value="{_cell(query.start_raw)}" placeholder="2026-10-18"></label>
<label>End<input name="end" value="{_cell(query.end_raw)}" placeholder="2026-10-18"></label>
<label>Page size<input name="page_size" value="{query.page_size}"></label>
<button type="submit">Filter</button>
</form>
<h2>Balances</h2>
<table>
<thead><tr><th>Account</th><th>Name</th><th>Type</th><th>Circle</th><th>Member</th><th>Balance (pence)</th><th>Balance</th>{change_headers}</tr></thead>
<tbody>
{"".join(balance_rows)}
</tbody>
</table>
<h2>Transactions</h2>
<table>
<thead><tr><th>Posted (UTC)</th><th>Entry</th><th>Description</th><th>Reference</th><th>Reverses</th><th>Account</th><th>Type</th><th>Direction</th><th>Pence</th><th>Amount</th><th>Memo</th></tr></thead>
<tbody>
{"".join(entry_rows)}
</tbody>
</table>
<p class="pager">{prev_link}<span>Page {query.page} of {pages} ({total} transactions)</span>{next_link}</p>
</body>
</html>
"""


def register_ledger_admin_routes(fastapi_app: FastAPI, get_current_user) -> None:
    """Platform-admin read API and page. No create, update, or delete route."""

    @fastapi_app.get("/api/v1/admin/ledger")
    def ledger_api(
        request: Request,
        response: Response,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        response.headers["Cache-Control"] = "no-store"
        query, balances, transactions, total = load_ledger(db, request, user)
        return {
            "balances": [_balance_payload(row) for row in balances],
            "transactions": [_transaction_payload(row) for row in transactions],
            "page": query.page,
            "page_size": query.page_size,
            "total": total,
        }

    @fastapi_app.get("/admin/ledger")
    def ledger_page(
        request: Request,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        query, balances, transactions, total = load_ledger(db, request, user)
        page = _render_page(query, balances, transactions, total)
        return HTMLResponse(page, headers={"Cache-Control": "no-store"})
