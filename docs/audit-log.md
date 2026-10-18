# Audit log

Security-relevant events are appended to `audit_log`. The log covers sign-in success and failure, logout, lockout, password reset, email verification, circle role changes, and payout-position changes. Later product flows call the same writer for contributions, Delay Cover, Early Payout, consent, profile and bank-detail changes, and data-rights requests. Reading the log is recorded too.

Times come from `clock.now()` (UTC). Tests move that clock with `freeze` and `advance`.

Use synthetic `@example.test` addresses only. Do not put real member data or the HMAC key in the repo.

## What is logged

| Action | When it is written |
|---|---|
| `sign_in_success`, `sign_in_failure` | Login. An unknown address and a wrong password both write a failure. The HTTP response stays the same 401. |
| `logout` | Logout. |
| `account_locked` | `record_lockout`, or an auth audit row whose action ends in `_lockout` (the rate-limit lockout notice). `after.auth_action` says `login`, `password_reset`, or `resend_verification`. |
| `rate_limited` | A signup, login, password reset, or verification resend refused by the per-IP cap, the per-account cap, or a lock that is already in effect. `after.auth_action` names which of those it was. The address is the HMAC only. |
| `password_reset_requested`, `password_reset_completed` | Forgot-password and a completed reset. |
| `email_verification_sent`, `email_verified`, `signup_existing_email` | Verification mail and a confirmed address. An existing address at sign-up writes `signup_existing_email`. |
| `role_changed` | `record_role_change`, in the same transaction as the membership change. |
| `payout_position_changed` | `record_position_change`. |
| `ajo_created`, `ajo_joined` | Creating or joining an Ajo. |
| `platform_role_changed` | `grant_platform_admin`. There is no HTTP route that grants this. |
| `audit_log_read`, `audit_log_denied` | A platform admin opened the log, or a signed-in user was refused. |
| Other names in `audit.LISTED_EVENTS` | `record_event` accepts them for the flows that are not built yet (contributions, Delay Cover, Early Payout, consent, exports, and so on). |

## Fields

Each row stores:

| Field | Meaning |
|---|---|
| `actor_user_id` | Who did it. Null when the address is unknown. |
| `actor_role` | Circle role or `platform_admin` when that is known. |
| `session_id` | Access-token session, when the request has one. |
| `request_id` | `X-Request-ID` when it is a short token, otherwise a generated id. |
| `ip` | `request.client.host` only. `X-Forwarded-For` is not read. |
| `user_agent` | The user-agent header, truncated. |
| `circle_id` | Ajo id, when the event belongs to one. |
| `action` | Event name. |
| `target_user_id` | The other user, when there is one. Sign-in uses the same user as the actor. |
| `email_hash` | HMAC-SHA256 of the normalised address under `AUDIT_EMAIL_HMAC_KEY`. |
| `before_values`, `after_values` | JSON before and after, already masked. |
| `created_at` | UTC time from `clock.now()`. |
| `prev_hash`, `entry_hash` | Hash chain. `canonical` is the exact JSON that was hashed. |

The first row has a null `prev_hash`. Every later row's `prev_hash` is the previous `entry_hash`. `entry_hash` is SHA-256 of `canonical`.

## Masking (SR-09)

The address is not stored. Callers pass it only so it can be hashed, and the hash is not plain SHA-256. Outside `local` and `dev`, a missing `AUDIT_EMAIL_HMAC_KEY` refuses the hash. On `local` or `dev`, a missing key is created in git-ignored `local/audit-email-hmac.key`.

Keys that name a password, token, secret, BVN, ethnicity, or bank detail are omitted. An email address inside a value is replaced with the HMAC. The log does not store a reset link, an access token, or a refresh token.

The admin page shows the first 12 hex characters of the email hash. It does not show a name or an address.

## Append-only

The application inserts rows. It has no update or delete route. `UPDATE` and `DELETE` on `audit_log` raise `audit_log is append-only` through a database trigger on SQLite and on Postgres, including when the connection is the table owner. The ORM raises the same error before it sends the statement.

A correction is a new row. Inserts take a row lock on `audit_chain_lock` so two writers do not share one previous hash.

A hash chain shows a gap or a changed body. Someone who can rewrite the whole table and recompute every hash can still forge a chain. Production should keep the database role able to insert and not able to disable triggers, and should keep backups.

## Who can read it

`GET /api/v1/admin/audit` and `GET /admin/audit` require a signed-in user whose `users.platform_role` is `platform_admin`. That column is read on the server. A circle admin is not a platform admin. A query, header, or body role is ignored.

Grant the role from the server, then commit:

```python
from audit import grant_platform_admin
grant_platform_admin(db, user_id=USER_ID, actor_user_id=ACTOR_ID)
```

There is no public route for that grant. A refused signed-in read writes `audit_log_denied` and returns 403. Opening the log writes `audit_log_read`.

## How to query it

Admin page (send the access token; the page does not accept the token in the query string):

```bash
curl -sS -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://127.0.0.1:8000/admin/audit?event_type=role_changed&page=1&page_size=50"
```

API, with filters for user, circle, event type, and date range. `start` and `end` are ISO dates or datetimes. An end date includes that UTC day. `page` starts at 1. `page_size` is 1 to 100.

```bash
curl -sS -H "Authorization: Bearer $ACCESS_TOKEN" \
  "http://127.0.0.1:8000/api/v1/admin/audit?user_id=1&circle_id=2&event_type=sign_in_failure&start=2026-10-01&end=2026-10-18&page=1&page_size=50"
```

The JSON body is `entries`, `page`, `page_size`, and `total`. Entries have no email field. Responses send `Cache-Control: no-store`.

Local SQLite (`sqlite:///local/ajo.db`):

```sql
SELECT id, created_at, action, actor_user_id, actor_role, target_user_id,
       circle_id, session_id, email_hash, ip
FROM audit_log
WHERE action = 'role_changed'
ORDER BY id;
```

```sql
SELECT id, prev_hash, entry_hash
FROM audit_log
ORDER BY id;
```

## Retention

Security sets the retention period before production (UK GDPR storage limitation and the FCA record). Proposal: keep these rows for six years from `created_at`, which covers a usual complaint and record-keeping window, then archive them outside this application. The app cannot delete them. A removal is an operator change with a new chain anchor, not an `DELETE` from the API. Do not use this table as a marketing or analytics store.
