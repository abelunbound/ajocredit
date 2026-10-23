# Ledger

The ledger is the append-only record of circle money. Alembic revision `0002_create_ledger` creates it. The same tables run on SQLite locally and on Postgres in CI.

Amounts are integer pence. `2575` is £25.75. There is no float or decimal money column. Divide by 100 only when showing pounds.

Use synthetic circle and member refs in local data. Do not put real member data in this database.

## Tables

### `ledger_accounts`

One row is one account in the chart. The code is permanent.

| Column | Type | Notes |
|---|---|---|
| `id` | integer | Primary key |
| `code` | string (128) | Unique, for example `asset:partner:circle-synth-example` |
| `name` | string (255) | Display name |
| `kind` | string (16) | `asset`, `liability`, `equity`, `income`, or `expense` |
| `currency` | string (3) | Three letters. Local circles use `GBP` |
| `circle_ref` | string (64), nullable | Synthetic circle id, when the account belongs to a circle |
| `member_ref` | string (64), nullable | Synthetic member id, when the account belongs to a member |
| `created_at` | timestamp with time zone | Set from `clock.now()` when the account is opened |

Assets and expenses are debit-normal: balance = debits − credits. Liabilities, equity, and income are credit-normal: balance = credits − debits.

### `ledger_entries`

One row is the header of a journal entry.

| Column | Type | Notes |
|---|---|---|
| `id` | integer | Primary key |
| `posted_at` | timestamp with time zone | Set from `clock.now()` when the entry is posted |
| `description` | string (500) | What the entry is for |
| `reference` | string (128), nullable | Optional unique id so the same event is not posted twice |
| `reversal_of_id` | integer, nullable | Set on a correction. Points at the original `ledger_entries.id`. Unique, so an original entry has at most one reversal. Ordinary entries leave this null, and many nulls are allowed |

### `ledger_lines`

One row is one side of an entry. An entry has at least two lines.

| Column | Type | Notes |
|---|---|---|
| `id` | integer | Primary key |
| `entry_id` | integer | Foreign key to `ledger_entries.id` |
| `account_id` | integer | Foreign key to `ledger_accounts.id` |
| `direction` | string (6) | `debit` or `credit` |
| `amount_pence` | bigint | Positive integer pence. Zero and fractions are rejected |
| `memo` | string (255), nullable | Optional line note |

## Double-entry

Every entry's lines sum to zero. Each line stores a positive `amount_pence` and a direction. Debit pence count as positive and credit pence count as negative. For a valid entry those signed amounts add up to `0`, which is the same rule as "total debits equal total credits".

A contribution of 2575 pence from member Ada into the partner clearing account is two lines:

- debit `asset:partner:…` 2575
- credit `liability:member-ada:…` 2575

Signed sum: `2575 + (−2575) = 0`.

The ledger is append-only. Rows are inserted and then left as they were. Updates and deletes are rejected in the application and by database triggers on all three tables (SQLite and Postgres). A mistake is fixed by a new reversing entry, not by editing the original. The reversal swaps debit and credit on each line, sets `reversal_of_id` to the original entry, and gets its own `posted_at`. The original lines stay in the history. `reversal_of_id` is unique, so two reversals of the same entry cannot both commit. After a reversal, the two entries together bring the affected accounts back to where they were, and each entry still sums to zero.

In production the application's database role should have only `INSERT` and `SELECT` on `ledger_accounts`, `ledger_entries`, and `ledger_lines`. Postgres triggers do not block `TRUNCATE`, so that role must not be able to truncate, update, or delete those tables.

## CI balance check

`backend.ledger_balance.check_ledger_invariants` reads posted rows and checks two rules, in integer pence. `python -m backend.ledger_balance --seed` posts a synthetic circle, prints the three totals, and exits 1 when either rule fails. The Postgres 16 API job runs that command after `alembic upgrade head`, with `AJO_ENV=ci`. A mismatch fails the job.

Seeding writes rows, so `--seed` runs only when `AJO_ENV` is `local`, `dev`, or `ci`. Letter case and surrounding space do not matter. An unset `AJO_ENV`, a blank value, or any other value prints a refusal and exits 1. The database is not opened and nothing is posted. `python -m backend.ledger_balance` without `--seed` only reads, and it runs in any environment.

The synthetic circle is `circle-synth-ci-balance`. Member refs are `member-ada` and `member-bo`. The seed has no email address and no bank detail. Accounts and entries go through `open_account`, `post_entry`, and `post_reversal`, so `created_at` and `posted_at` come from `clock.now()`. One contribution is posted by mistake and then reversed. The reversal sets `reversal_of_id`. The original row stays. Calling the seed again does not post a second copy.

1. Every posted transaction balances. For each `ledger_entries` row, including a reversal, debit pence equal credit pence and there are at least two lines. Each entry is checked on its own. Two unbalanced entries can still cancel in the account totals.
2. The accounts reconcile: **money in = money out + balances**.
   - **Money in** is the signed balances of liability, equity, and income (credit-normal: credits − debits).
   - **Money out** is the signed balances of expense accounts (debit-normal: debits − credits).
   - **Balances** is the signed balances of asset accounts (debit-normal: debits − credits).

An empty ledger passes (`0 = 0 + 0`). The CI seed is not empty.

| Entry | Debit | Credit |
|---|---|---|
| Equity opening | asset 1000 | equity 1000 |
| Ada contribution | asset 2575 | liability Ada 2575 |
| Bo contribution | asset 5000 | liability Bo 5000 |
| Fee | expense 75 | asset 75 |
| Interest | asset 25 | income 25 |
| Mistaken Ada contribution | asset 100 | liability Ada 100 |
| Reversal of that mistake | liability Ada 100 | asset 100 |

Asset balance 8525. Liabilities 7575. Equity 1000. Income 25. Expense 75. Money in 8600, money out 75, balances 8525. `8600 = 75 + 8525`.

`post_entry` rejects an unbalanced entry before it is stored. A raw `INSERT` can still store one, because the table checks allow any positive pence amount. `tests/test_ledger_balance.py` inserts a broken fixture that way, asserts the checker fails, and rolls the insert back. One fixture is a single entry whose debits and credits differ, so the equation fails too. The other is a pair of unbalanced entries that cancel in the totals. The per-entry rule catches that pair. Either mismatch fails the same check the Postgres job runs.

## Posting time

`ledger_accounts.created_at` and `ledger_entries.posted_at` are set from `clock.now()`.

`clock.now()` returns a timezone-aware UTC datetime. The default is the wall clock. Tests move it with `clock.freeze`, `clock.advance`, and `clock.reset`, then call `clock.restore_for_tests()` to put the wall clock back. Production always uses the wall clock. A loopback dev process can move time only when `ALLOW_TEST_CLOCK` is set and `AJO_ENV` is `local` or `dev`.

## View the ledger locally

Create the local SQLite file and the tables:

```bash
DATABASE_URL=sqlite:///local/ajo.db alembic upgrade head
```

`local/ajo.db` is git-ignored. It holds synthetic data only.

### sqlite3

```bash
sqlite3 local/ajo.db
```

```sql
.tables
SELECT id, code, kind, circle_ref, member_ref FROM ledger_accounts;
SELECT id, posted_at, description, reference, reversal_of_id FROM ledger_entries;
```

### DB Browser for SQLite

1. Install [DB Browser for SQLite](https://sqlitebrowser.org/).
2. Choose **File → Open Database**.
3. Open `local/ajo.db` in the repo's `local/` directory (the file from `alembic upgrade head` above).
4. Use **Browse Data** and pick `ledger_accounts`, `ledger_entries`, or `ledger_lines`.
5. Use **Execute SQL** for the queries below.

The same SQL runs on the CI Postgres database. Amounts stay in integer pence in both places.

## Example queries

These use the synthetic refs `circle-synth-example` and `member-ada`. Replace them with the refs in your local file.

Entries that do not sum to zero (this should return no rows):

```sql
SELECT
  entry_id,
  SUM(CASE WHEN direction = 'debit' THEN amount_pence ELSE -amount_pence END) AS net_pence
FROM ledger_lines
GROUP BY entry_id
HAVING SUM(CASE WHEN direction = 'debit' THEN amount_pence ELSE -amount_pence END) <> 0;
```

A circle's account balances, in pence:

```sql
SELECT
  a.code,
  a.kind,
  a.member_ref,
  COALESCE(SUM(
    CASE
      WHEN a.kind IN ('asset', 'expense') AND l.direction = 'debit' THEN l.amount_pence
      WHEN a.kind IN ('asset', 'expense') AND l.direction = 'credit' THEN -l.amount_pence
      WHEN l.direction = 'credit' THEN l.amount_pence
      ELSE -l.amount_pence
    END
  ), 0) AS balance_pence
FROM ledger_accounts AS a
LEFT JOIN ledger_lines AS l ON l.account_id = a.id
WHERE a.circle_ref = 'circle-synth-example'
GROUP BY a.id, a.code, a.kind, a.member_ref
ORDER BY a.code;
```

The partner asset row is the pence still held for that circle. A member liability row is the net pence that member has paid in and not yet been paid out.

## Admin view

`GET /admin/ledger` is a read-only page for a platform admin. The server reads `users.platform_role`. The only value that can open the page is `platform_admin`. A circle admin, a circle member, a missing session, and a role in the query string or headers are refused. Denied means no balances and no transactions are returned.

The page lists account balances and the transactions (journal entries) with each of their lines. Both figures are added up from `ledger_lines` when the page is opened. There is no stored balance. Amounts stay integer pence, and the display columns are those integers shown in pounds (`2575` is £25.75). Divide by 100 only for that display.

**Balance** is every entry on the account from the beginning up to the end date. The end of that date is inclusive. When no end date is set, Balance runs up to `clock.now()` instead, so an entry posted after now is not included. The columns are `Balance (pence)` and `Balance`.

**Change in period** is the entries whose `posted_at` falls inside the date range: on or after the start date, and on or before the same end point used for Balance (the end date, or `clock.now()` when no end date is set). The columns are `Change in period (pence)` and `Change in period`. They are shown only when a start date is set.

Filters are circle (`circle_ref`), member (`member_ref`), account type (`asset`, `liability`, `equity`, `income`, or `expense`), and an inclusive UTC date range on `posted_at` (`start` and `end` as `YYYY-MM-DD`). Transactions are paginated (`page`, `page_size`, at most 100) and are limited to that same date range. A transaction that matches still shows every line, including the other side, so the entry on screen still sums to zero.

Suppose member Ada's liability is credited 1000 pence on 1 April and 2575 pence on 15 May, and `clock.now()` is 1 July.

| Dates | Balance | Change in period |
|---|---|---|
| none | 3575 | omitted |
| start 2026-05-01 only | 3575 | 2575 |
| end 2026-04-30 only | 1000 | omitted |
| start 2026-05-01 and end 2026-05-31 | 3575 | 2575 |

The form uses GET. There is no create, edit, or delete control, and no POST, PUT, PATCH, or DELETE route.

Opening the page calls `audit.record_event`. The action is `financial_data_viewed`. `created_at` is `clock.now()`. The row is appended to `audit_log`. No email address is stored. `after` records the view and the filters: circle, member, account type, start, end, page, and page size. The gate is `audit.is_platform_admin`.

## Admin API

`GET /api/v1/admin/ledger` uses the same gate, filters, pagination, and audit row as the page. Unknown query parameters are ignored, including `role`.

Example, with a synthetic circle ref:

```bash
curl -sS -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://127.0.0.1:8000/api/v1/admin/ledger?circle=circle-synth-example&member=member-ada&account_type=liability&start=2026-01-01&end=2026-01-31&page=1&page_size=50"
```

A successful body looks like this. `balance_pence` and `amount_pence` are integers. `balance_display` and `amount_display` are the same integers shown in pounds. `balance_pence` is Balance: every entry from the beginning through the end date, or through `clock.now()` when `end` is omitted. `change_in_period_pence` and `change_in_period_display` are Change in period. They are present only when `start` is set. `total` counts transactions, not lines.

```json
{
  "balances": [
    {
      "account_id": 2,
      "code": "liability:member-ada:circle-synth-example",
      "name": "Member Ada contributions",
      "account_type": "liability",
      "currency": "GBP",
      "circle": "circle-synth-example",
      "member": "member-ada",
      "balance_pence": 2575,
      "balance_display": "£25.75",
      "change_in_period_pence": 2575,
      "change_in_period_display": "£25.75"
    }
  ],
  "transactions": [
    {
      "id": 1,
      "posted_at": "2026-01-15T12:00:00+00:00",
      "description": "Contribution",
      "reference": "contrib-synth-1",
      "reversal_of_id": null,
      "entries": [
        {
          "id": 1,
          "account_id": 1,
          "account_code": "asset:partner:circle-synth-example",
          "account_type": "asset",
          "circle": "circle-synth-example",
          "member": null,
          "direction": "debit",
          "amount_pence": 2575,
          "amount_display": "£25.75",
          "memo": null
        },
        {
          "id": 2,
          "account_id": 2,
          "account_code": "liability:member-ada:circle-synth-example",
          "account_type": "liability",
          "circle": "circle-synth-example",
          "member": "member-ada",
          "direction": "credit",
          "amount_pence": 2575,
          "amount_display": "£25.75",
          "memo": null
        }
      ]
    }
  ],
  "page": 1,
  "page_size": 50,
  "total": 1
}
```

`401` means there is no signed-in session. `403` with detail `Not allowed.` means the signed-in user is not a platform admin. `422` means a filter is invalid (unknown account type, a bad date, `end` before `start`, or a page outside `1..100` for `page_size`). The response is `Cache-Control: no-store`.

`users.platform_role` is the column added by Alembic revision `0008_audit_log`. There is no ledger request that grants it. It is null for everyone else.

One member's history in that circle, oldest first:

```sql
SELECT
  e.posted_at,
  e.id AS entry_id,
  e.description,
  e.reference,
  e.reversal_of_id,
  l.direction,
  l.amount_pence,
  l.memo
FROM ledger_lines AS l
JOIN ledger_entries AS e ON e.id = l.entry_id
JOIN ledger_accounts AS a ON a.id = l.account_id
WHERE a.circle_ref = 'circle-synth-example'
  AND a.member_ref = 'member-ada'
ORDER BY e.posted_at, e.id, l.id;
```
