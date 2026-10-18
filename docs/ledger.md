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
| `reversal_of_id` | integer, nullable | Set on a correction. Points at the original `ledger_entries.id` |

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

The ledger is append-only. Rows are inserted and then left as they were. Updates and deletes are rejected in the application and by database triggers on all three tables (SQLite and Postgres). A mistake is fixed by a new reversing entry, not by editing the original. The reversal swaps debit and credit on each line, sets `reversal_of_id` to the original entry, and gets its own `posted_at`. The original lines stay in the history. After a reversal, the two entries together bring the affected accounts back to where they were, and each entry still sums to zero.

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
