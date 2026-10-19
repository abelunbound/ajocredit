# How the app uses the API

Dash and FastAPI are two processes. The browser talks to Dash. Dash's server calls the FastAPI API on the user's behalf. The origin is `AJO_API_BASE`.

Access tokens and refresh tokens stay in the Dash process. They are not sent to the browser, not stored in `localStorage`, and not written to the application log. The browser cookie holds an opaque session id.

Sign-in, refresh, logout, and the rate limits are described in [docs/auth.md](auth.md). This page does not repeat them.

## Timeouts and outages

Every Dash call to the API uses one 4 second timeout.

A connection error, a timeout, or a 5xx response shows **Service unavailable, please try again shortly** on the page. The visitor stays signed in. Dash does not drop the session for an outage.

## Error codes

| Status | Meaning |
|---|---|
| 401 | Not signed in, or the access token has expired. Dash tries one refresh, then treats the call as signed out if that refresh fails. |
| 403 | The stored role is not allowed to do this. |
| 404 | Not in that circle, or the record was not found. |
| 429 | Rate limited. The limits and the lockout are in [docs/auth.md](auth.md). |
| 5xx | The API is having an outage. The page shows the message above and the user stays signed in. |

## Routes

Product routes live under `/api/v1`. The paths below are the ones the API registers. Names in `{braces}` are the path parameters in the code.

### Auth

See [docs/auth.md](auth.md).

- `POST /api/v1/auth/signup`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/sessions`
- `DELETE /api/v1/auth/sessions/{session_id}`
- `POST /api/v1/auth/password/forgot`
- `POST /api/v1/auth/password/reset`
- `POST /api/v1/auth/verification/resend`
- `POST /api/v1/auth/verification/confirm`
- `GET /api/v1/me`

### Circles and roles

- `GET /api/v1/circles`
- `POST /api/v1/circles`
- `POST /api/v1/circles/{circle_id}/join`
- `GET /api/v1/circles/{circle_id}`
- `POST /api/v1/circles/{circle_id}/members/{user_id}/role`

A role change is written to the audit log. See [docs/audit-log.md](audit-log.md).

### Payouts

- `GET /api/v1/circles/{circle_id}/payouts`

A member of the circle who is not an admin for it receives 403. Someone who is not in the circle receives 404.

### Admin audit

See [docs/audit-log.md](audit-log.md).

- `GET /api/v1/admin/audit`

The same process also serves the HTML page `GET /admin/audit`. That path is outside `/api/v1`.

### Admin ledger

See [docs/ledger.md](ledger.md).

- `GET /api/v1/admin/ledger`

The same process also serves the HTML page `GET /admin/ledger`. That path is outside `/api/v1`.

### Other routes the process registers

`GET /health` checks the database. It is not under `/api/v1`.

`GET /api/v1/dev/clock` and `POST /api/v1/dev/clock` are registered only when the dev clock control is allowed (loopback, `ALLOW_TEST_CLOCK`, and `AJO_ENV` of `local` or `dev`). Otherwise those paths are not routes.

## Run it locally

Use synthetic `@example.test` data only. `admintest` and `membertest` are the only accounts that sign in on a laptop.

1. API, on http://localhost:8000:

   ```bash
   uvicorn api:app --reload --no-proxy-headers
   ```

2. Dash, on http://localhost:8055, with:

   ```bash
   AJO_API_BASE=http://localhost:8000
   AJO_ENV=local
   ```

The live reference is on the API port, not the Dash port:

- http://localhost:8000/docs
- http://localhost:8000/redoc
- http://localhost:8000/openapi.json

Those three are switched off unless `AJO_ENV` (trimmed, case-insensitive) is `local` or `dev`. Unset, `prod`, `staging`, and any other value make all three respond with 404.

## Forgot and reset password

`/signin` opens an email form and calls `POST /api/v1/auth/password/forgot`. The screen shows one message whether or not that email exists. `/reset-password` calls `POST /api/v1/auth/password/reset` with the token in the JSON body. Settings **Email reset link** uses the same forgot call for the signed-in account.

To try it on a laptop, run the API and Dash as above with `AJO_ENV=local` and `EMAIL_SENDER=dev`. Use an `@example.test` address. Open the newest file in `local/email-inbox` (git-ignored). The link starts with `PUBLIC_APP_URL`, which defaults to `http://localhost:8055`, and ends with `#token=`. The page removes that fragment from the address bar on load.

## Try the outage message

1. Sign in as `membertest`.
2. Stop the API with Ctrl+C.
3. Open `/members` and `/dashboard`.
4. Restart the API.

Both pages show **Service unavailable, please try again shortly**, and you stay signed in. After the API is running again, reload either page.
