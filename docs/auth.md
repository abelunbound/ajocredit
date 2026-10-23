# Authentication

Sign-up, sign-in, refresh, logout, password reset, and email verification live under `/api/v1`. Time checks use `clock.now()`. A real email provider is not part of this build. That arrives later in #123. Until then, mail is the local test inbox described below, or the email endpoints fail closed.

Use synthetic `@example.test` addresses only. Do not put real member data, passwords, or keys in the repo.

Laptop setup, the dev inbox, and sign-in failures are in [resetetc.md](resetetc.md).

## Sign-in (#33)

Emails are trimmed and lowercased before they are stored and before login. The unique column is that normalised address.

| Method and path | What it does |
|---|---|
| `POST /api/v1/auth/signup` | Stores a bcrypt hash. Returns the same 201 body whether or not the email is already registered. A duplicate does not change the existing password. |
| `POST /api/v1/auth/login` | Returns an access token and a refresh token. An unknown email and a wrong password both return the same 401. The missing-user path still runs a bcrypt check. |
| `POST /api/v1/auth/refresh` | Consumes the presented refresh token and returns a new pair. |
| `POST /api/v1/auth/logout` | Revokes that session and its refresh tokens. An expired access token is still accepted so the session can be ended. |
| `GET /api/v1/auth/sessions` | Lists this user's live sessions. |
| `DELETE /api/v1/auth/sessions/{session_id}` | Revokes one of this user's sessions. |
| `GET /api/v1/me` | Returns `user_id`, `name`, `email`, and `email_verified` for the access token's session. |

Passwords must be at least 8 characters and at most 72 bytes. The access token is a PyJWT HS256 token. It carries the user id and the session id. It does not carry the email. `JWT_EXPIRY_DAYS` is ignored.

Access tokens last 15 minutes by default (`ACCESS_TOKEN_MINUTES`, from 1 to 60). Refresh tokens last 14 days by default (`REFRESH_TOKEN_DAYS`, from 1 to 30). Only the SHA-256 hash of a refresh token is stored. The raw token is `secrets.token_urlsafe` and is not stored.

Each refresh is one conditional update: the row is marked revoked only while it is unused and unexpired. If that update does not change exactly one row, the request is rejected. A second use of a rotated refresh token fails and revokes the whole session, including the replacement token.

`exp`, `iat`, and `nbf` are checked against `clock.now()`, with a 10-second leeway. PyJWT's own clock checks are off, so moving the test clock does not reject a token that was just issued. A token whose `iat` or `nbf` is still in the future after that leeway is rejected.

Signup, login, password reset, and verification resend all call `enforce_auth_attempt_policy` in `backend/auth.py`. That is the only limiter on those routes. It reads `request.client.host` only. `X-Forwarded-For` is not trusted. The limits and the lockout are described below.

## Rate limits and lockout (#40)

Each of signup, login, password reset, and verification resend is counted twice: once for the client IP, and once for the account. The account key is the HMAC-SHA256 of the normalised email, the same hash as the audit log. The raw address is not stored in `auth_rate_buckets` or `auth_account_guards`.

The window is 15 minutes of `clock.now()`. A window that has expired starts again at zero. These are the caps whenever `AJO_ENV` is unset or is anything other than `local` or `dev`:

| Action | Per IP | Per account |
|---|---|---|
| Signup | 20 | 5 |
| Login | 50 | 20 |
| Password reset | 20 | 5 |
| Verification resend | 20 | 5 |

`local` and `dev` use a higher cap, 10000 per IP and 100 per account, so a laptop and the test suite are not blocked. Those two environments keep their own counters (`ip-dev` and `account-dev`). Any other value, including an empty `AJO_ENV`, uses the table above. The higher caps cannot be turned on by another variable.

A request over either cap returns 429 with `Too many attempts. Try again later.` The body is the same for a known address and an unknown one, and it does not contain the email. Login still runs a bcrypt check on that path, so a locked or limited known address takes the same time as an unknown one. Both return that same 429.

The per-account cap of 5 for password reset and verification resend is the production rule. It means five messages are sent. The fifth request succeeds. The sixth request in that window is limited. Because that production cap is also the first lockout step, reset and resend do not lock on the fifth message. In `local` and `dev` the account cap is 100, so that first lock step can still refuse the fifth request and only four emails go out. The later lock steps, 10 and 20, still apply. Login still locks on the fifth failed password.

Login, password reset, and verification resend also lock the account. Failed attempts are counted on `auth_account_guards`. A login counts only after the password check fails, so a correct password is not a failure. Reset and resend count each request that asks for a message. A quiet 24 hours with no lock in force clears that streak. A lock lasts 1 minute, then 15 minutes, then 1 hour. Further steps stay at 1 hour. The lock is checked with `clock.now()`. While it is in force, a new request for a message returns the same 429 and does not add another failure. A successful login clears the login streak. A completed reset clears the reset streak. Confirming the email clears the resend streak. The per-IP window is not cleared by success.

`POST /api/v1/auth/password/reset` with a valid token skips the per-account cap and the lockout. It still counts toward the per-IP cap. Requests for a reset link cannot use up the account allowance and then block the link. An invalid token is rejected before the limiter runs.

The lockout notice is sent through the same mail sender as password reset, and only when that address has a user row. The message does not include a token or the address. One notice is sent per new lock level. An audit row stores the HMAC, the user id when there is one, and the client IP. If the audit key is missing, these routes return 503 and do not fall back to a plain hash.

## Password reset (#114)

| Method and path | What it does |
|---|---|
| `POST /api/v1/auth/password/forgot` | Always returns the same message, whether or not the email is registered. |
| `POST /api/v1/auth/password/reset` | Sets a new bcrypt hash when the link is still valid. |

The reset token is `secrets.token_urlsafe`. Only its SHA-256 hash is stored. It expires 30 minutes after `clock.now()`. The presented token is consumed by one conditional update, so a second use fails. A successful reset revokes every session and refresh token for that user, and marks any other open reset links used.

The link is `{PUBLIC_APP_URL}/reset-password#token=<token>`. The token sits in the URL fragment so a server access log does not record it. `reset_link` reads `PUBLIC_APP_URL` only. It does not read the request Host header. When `PUBLIC_APP_URL` is unset, the origin is the Dash app at `http://localhost:8055`.

Dash **Forgot password?** on `/signin` opens an email form and calls `POST /api/v1/auth/password/forgot`. The page shows `If an account exists for that email, a reset link is on its way.` whether or not the address is registered. A 429 shows the API's own `detail`. `/reset-password` reads `#token=`, removes that fragment with `history.replaceState` as the page loads, and sends the token only in the reset POST body. It is not written to the application log. An expired or used link, and a 429, show the API `detail` as returned. Success sends the visitor to `/signin`, because every session has ended. Settings **Email reset link** calls the same forgot route for the signed-in account and shows that same message.

On a laptop, set `AJO_ENV=local` and `EMAIL_SENDER=dev`, request a link, and open the newest file under `local/email-inbox`. Paste that link into the browser on the Dash origin.

Audit rows in `auth_audit_events` store an HMAC-SHA256 of the email, the user id when there is one, and the client IP. They do not store the address, the token, the link, or the password. The hash is not plain SHA-256.

## Email verification (#115)

Sign-up sends a verification link through the same sender as password reset. The HTTP body of sign-up stays generic. An address that is already registered gets a message with no token.

| Method and path | What it does |
|---|---|
| `POST /api/v1/auth/verification/resend` | Always returns the same message, whether or not the email is registered. A new link is sent only when the account exists and is not yet verified. |
| `POST /api/v1/auth/verification/confirm` | Sets `email_verified_at` when the link is still valid. |
| `POST /api/v1/circles` | Creates an Ajo. Rejected until the email is verified. |
| `POST /api/v1/circles/{id}/join` | Joins an Ajo. Rejected until the email is verified. |

The verification token is `secrets.token_urlsafe`. Only its SHA-256 hash is stored. It expires 24 hours after `clock.now()`. The presented token is consumed by one conditional update, so a second use fails. The link is `{PUBLIC_APP_URL}/verify-email#<token>`. It is built only from `PUBLIC_APP_URL`, not from the request Host header.

Dash `/verify-email` reads that fragment, removes it from the address bar with `history.replaceState` on load, and posts the token only in `POST /api/v1/auth/verification/confirm`. The page shows the API `detail` for success, an expired or used link, and 429. It links to `/signin`. The token is not written to the application log.

An unverified user can log in and call `GET /api/v1/me` (`email_verified` is false). Creating or joining an Ajo is blocked on the server with 403 and the detail `Verify your email before creating or joining an Ajo.` The check runs before the circle is looked up. The Join Ajo page and the Create Ajo row show that same prompt when the session says the address is not verified.

Seeded `admintest` and `membertest` API users are stored already verified. Other seeded circle members count as pre-verified unless `email_verified` is set to false on that member.

## Local demo sign-in

On a laptop, the only demo accounts that can sign in are `admintest` and `membertest`. Their API emails are `admintest@example.test` and `membertest@example.test`. Passwords come from the git-ignored stub credentials file (`STUB_USERS_FILE`, default `local/stub-users.json`). They are not in the repo.

`SEED_DEMO_ACCOUNTS` must be on, and `AJO_ENV` must be `local` or `dev`, or those rows are not created. If the flag is on while `AJO_ENV` is unset or is anything else, the API and the Dash app refuse to start. There is no pytest exception. The flag being off does not seed and does not stop startup.

The ten demo personas are display data for the UI. They have no user rows and no passwords in the database, so they cannot sign in.

The older Dash stub (`ALLOW_LOCAL_STUB_LOGIN`) is separate. It also knows only `admintest` and `membertest`. It is allowed only on a loopback bind (`127.0.0.1`, `localhost`, or `::1`) when `AJO_ENV` is unset or `local`. Enabling it anywhere else refuses to start. The stub is what the test suite uses when `AJO_API_BASE` is unset. With `AJO_API_BASE` set, Dash does not use that stub.

## Dash calls the API

Set `AJO_API_BASE` to the API origin, for example `http://127.0.0.1:8000`. `./utils/dev-launch-local.sh` starts the API on port 8000 and Dash on port 8055, and it reads `.env` from the repo root. The Dash process is `python frontend/app_dash_web.py`, which uses `http://127.0.0.1:8000` when `AJO_API_BASE` is unset.

Dash signs in with `POST /api/v1/auth/login`, reads `GET /api/v1/me`, and loads circles with `GET /api/v1/circles` and `GET /api/v1/circles/{id}`. The role on the page is the membership role from those responses. A username is not turned into a role. Payouts calls `GET /api/v1/circles/{id}/payouts`. Admin calls `GET /api/v1/admin/audit` and `GET /api/v1/admin/ledger`. Create, join, and logout use the existing POST routes.

The access token and the refresh token stay in the Dash process. The browser cookie holds an opaque id. Tokens are not written to the application log, to the address bar, or to `localStorage`. A 401 sends the refresh token once to `POST /api/v1/auth/refresh` and then retries. Only `admintest` and `membertest` can sign in through the UI, and only when `AJO_ENV` is `local` or `dev`.

## Dev inbox

There is no real email provider, account, or API key in this build. A provider is #123.

When `AJO_ENV` is `local` or `dev`, and `EMAIL_SENDER` is empty or one of `dev`, `file`, `inbox`, or `console`, messages go to an in-memory list and, outside pytest, to git-ignored files under `local/email-inbox` (override with `AJO_EMAIL_INBOX`). Tests stay in memory unless `AJO_EMAIL_INBOX` is set.

Setting `EMAIL_SENDER` to one of those dev values when `AJO_ENV` is unset, or is not `local` or `dev`, refuses to start. If the dev sender is not selected and `AJO_ENV` is not `local` or `dev`, the process can start, but sign-up, forgot-password, and resend return 503 and write nothing. That is the fail-closed path until #123 configures a real provider.

## Logs (SR-09)

Do not write passwords, reset tokens, verification tokens, refresh tokens, access tokens, or the links that carry them to the application log. Do not write the raw email there either. The dev inbox stores the message body for local testing. That copy is git-ignored and is not a log line. Validation errors do not echo the submitted password. Audit rows and rate-limit rows store the HMAC of the email, not the email.

## Environment variables

| Variable | Required | Default | Rule |
|---|---|---|---|
| `JWT_SECRET_KEY` | Yes, for the API | — | At least 32 characters. The example placeholder refuses to start. |
| `DATABASE_URL` | Yes, for the API | — | SQLite locally. Postgres in CI. Missing value refuses to start. |
| `AJO_ENV` | No | unset | `local` or `dev` is a laptop. Unset is not local. Any other value is a deploy. |
| `ACCESS_TOKEN_MINUTES` | No | `15` | Capped at 1–60. `JWT_EXPIRY_DAYS` is ignored. |
| `REFRESH_TOKEN_DAYS` | No | `14` | Capped at 1–30. |
| `PUBLIC_APP_URL` | No | `http://localhost:8055` | Dash origin used in reset and verification links. Not the request Host header. |
| `EMAIL_SENDER` | No | empty | Empty or `dev` / `file` / `inbox` / `console` uses the dev inbox on `local` or `dev` only. Those values anywhere else refuse to start. |
| `AJO_EMAIL_INBOX` | No | `local/email-inbox` | Git-ignored folder for the dev inbox. Under pytest, files are written only when this is set. |
| `AUDIT_EMAIL_HMAC_KEY` | Outside local and dev | — | HMAC key for audit email hashes. On `local` or `dev`, a missing key is created in git-ignored `local/audit-email-hmac.key`. Otherwise hashing fails closed (HTTP 503, no plain SHA-256). |
| `AUDIT_EMAIL_HMAC_KEY_FILE` | No | `local/audit-email-hmac.key` | Where the local key file is created. Do not commit it. |
| `SEED_DEMO_ACCOUNTS` | No | `false` | `1`, `true`, `yes`, or `on` seeds `admintest` and `membertest`. Refuses to start unless `AJO_ENV` is `local` or `dev`. |
| `STUB_USERS_FILE` | No | `local/stub-users.json` | Git-ignored passwords for those two accounts. The example file is refused. |
| `ALLOW_LOCAL_STUB_LOGIN` | No | `false` | Dash stub for the same two names. Loopback and `AJO_ENV` unset or `local` only. Otherwise refuses to start. |
| `DASH_HOST` | No | `127.0.0.1` | Must be `127.0.0.1`, `localhost`, or `::1` when the Dash stub or the dev clock control is on. |
| `ALLOW_TEST_CLOCK` | No | `false` | Off is fine. On is refused outside pytest and a loopback process with `AJO_ENV` of `local` or `dev`. Production and staging cannot move time. |

Truthy flags accept `1`, `true`, `yes`, and `on`.
