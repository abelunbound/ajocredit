# Authentication

Sign-up, sign-in, refresh, logout, password reset, and email verification live under `/api/v1`. Time checks use `clock.now()`. A real email provider is not part of this build. That arrives later in #123. Until then, mail is the local test inbox described below, or the email endpoints fail closed.

Use synthetic `@example.test` addresses only. Do not put real member data, passwords, or keys in the repo.

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

Signup, login, password reset, and verification resend all call `enforce_auth_attempt_policy` in `auth.py`. That function does not rate-limit or lock accounts yet. Full limiting stays in #40. It reads `request.client.host` only. `X-Forwarded-For` is not trusted.

## Password reset (#114)

| Method and path | What it does |
|---|---|
| `POST /api/v1/auth/password/forgot` | Always returns the same message, whether or not the email is registered. |
| `POST /api/v1/auth/password/reset` | Sets a new bcrypt hash when the link is still valid. |

The reset token is `secrets.token_urlsafe`. Only its SHA-256 hash is stored. It expires 30 minutes after `clock.now()`. The presented token is consumed by one conditional update, so a second use fails. A successful reset revokes every session and refresh token for that user, and marks any other open reset links used.

The link is `{PUBLIC_APP_URL}/reset-password#<token>`. The token sits in the URL fragment so a server access log does not record it.

Audit rows in `auth_audit_events` store an HMAC-SHA256 of the email, the user id when there is one, and the client IP. They do not store the address, the token, the link, or the password. The hash is not plain SHA-256.

## Email verification (#115)

Sign-up sends a verification link through the same sender as password reset. The HTTP body of sign-up stays generic. An address that is already registered gets a message with no token.

| Method and path | What it does |
|---|---|
| `POST /api/v1/auth/verification/resend` | Always returns the same message, whether or not the email is registered. A new link is sent only when the account exists and is not yet verified. |
| `POST /api/v1/auth/verification/confirm` | Sets `email_verified_at` when the link is still valid. |
| `POST /api/v1/circles` | Creates an Ajo. Rejected until the email is verified. |
| `POST /api/v1/circles/{id}/join` | Joins an Ajo. Rejected until the email is verified. |

The verification token is `secrets.token_urlsafe`. Only its SHA-256 hash is stored. It expires 24 hours after `clock.now()`. The presented token is consumed by one conditional update, so a second use fails. The link is `{PUBLIC_APP_URL}/verify-email#<token>`.

An unverified user can log in and call `GET /api/v1/me` (`email_verified` is false). Creating or joining an Ajo is blocked on the server with 403 and the detail `Verify your email before creating or joining an Ajo.` The check runs before the circle is looked up. The Join Ajo page and the Create Ajo row show that same prompt when the session says the address is not verified.

Seeded `admintest` and `membertest` API users are stored already verified. Other seeded circle members count as pre-verified unless `email_verified` is set to false on that member.

## Local demo sign-in

On a laptop, the only demo accounts that can sign in are `admintest` and `membertest`. Their API emails are `admintest@example.test` and `membertest@example.test`. Passwords come from the git-ignored stub credentials file (`STUB_USERS_FILE`, default `local/stub-users.json`). They are not in the repo.

`SEED_DEMO_ACCOUNTS` must be on, and `AJO_ENV` must be `local` or `dev`, or those rows are not created. If the flag is on while `AJO_ENV` is unset or is anything else, the API and the Dash app refuse to start. There is no pytest exception. The flag being off does not seed and does not stop startup.

The ten demo personas are display data for the UI. They have no user rows and no passwords in the database, so they cannot sign in.

The older Dash stub (`ALLOW_LOCAL_STUB_LOGIN`) is separate. It also knows only `admintest` and `membertest`. It is allowed only on a loopback bind (`127.0.0.1`, `localhost`, or `::1`) when `AJO_ENV` is unset or `local`. Enabling it anywhere else refuses to start.

## Dev inbox

There is no real email provider, account, or API key in this build. A provider is #123.

When `AJO_ENV` is `local` or `dev`, and `EMAIL_SENDER` is empty or one of `dev`, `file`, `inbox`, or `console`, messages go to an in-memory list and, outside pytest, to git-ignored files under `local/email-inbox` (override with `AJO_EMAIL_INBOX`). Tests stay in memory unless `AJO_EMAIL_INBOX` is set.

Setting `EMAIL_SENDER` to one of those dev values when `AJO_ENV` is unset, or is not `local` or `dev`, refuses to start. If the dev sender is not selected and `AJO_ENV` is not `local` or `dev`, the process can start, but sign-up, forgot-password, and resend return 503 and write nothing. That is the fail-closed path until #123 configures a real provider.

## Logs (SR-09)

Do not write passwords, reset tokens, verification tokens, refresh tokens, access tokens, or the links that carry them to the application log. The dev inbox stores the message body for local testing. That copy is git-ignored and is not a log line. Validation errors do not echo the submitted password. Audit rows store the HMAC of the email, not the email.

## Environment variables

| Variable | Required | Default | Rule |
|---|---|---|---|
| `JWT_SECRET_KEY` | Yes, for the API | — | At least 32 characters. The example placeholder refuses to start. |
| `DATABASE_URL` | Yes, for the API | — | SQLite locally. Postgres in CI. Missing value refuses to start. |
| `AJO_ENV` | No | unset | `local` or `dev` is a laptop. Unset is not local. Any other value is a deploy. |
| `ACCESS_TOKEN_MINUTES` | No | `15` | Capped at 1–60. `JWT_EXPIRY_DAYS` is ignored. |
| `REFRESH_TOKEN_DAYS` | No | `14` | Capped at 1–30. |
| `PUBLIC_APP_URL` | No | `http://127.0.0.1:8000` | Origin used in reset and verification links. |
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
