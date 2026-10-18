# AjoFinance

A community finance platform built with Plotly Dash and FastAPI.

## Prerequisites

- Python 3.12+
- SQLite, which ships with Python, for the local FastAPI database
- PostgreSQL 16 when you run the API the way CI does, and later on GCP Cloud SQL

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/abelunbound/ajocredit.git
cd ajocredit
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install dependencies

For production:
```bash
pip install -r requirements.txt
```

For development (includes testing tools):
```bash
pip install -r requirements.txt -r requirements-dev.txt
```

### 4. Environment configuration

AjoFinance loads secrets and runtime settings from environment variables. Never hardcode secrets in code.

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and fill in real values:
   - **`JWT_SECRET_KEY`** (required by the API): a random string of at least 32 characters. Do not use the placeholder from `.env.example`.
     Generate one: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
   - **`DATABASE_URL`** (required by the API): local SQLite, `sqlite:///local/ajo.db`. That file is git-ignored and holds synthetic data only. The same setting is a PostgreSQL URL in CI and, later, on GCP Cloud SQL.
   - **`ACCESS_TOKEN_MINUTES`** (optional): access-token lifetime in minutes, 1 to 60 (default `15`). There is no 30-day JWT.
   - **`REFRESH_TOKEN_DAYS`** (optional): refresh-token lifetime in days, 1 to 30 (default `14`). Only a hash is stored.
   - **`DASH_DEBUG`** (optional): set to `true` only for local development (default `false`)
   - **`DASH_HOST`** (optional): Dash bind address (default `127.0.0.1`)
   - **`DASH_PORT`** (optional): Dash port (default `8055`)
   - **`AJO_ENV`** (optional): `local` on a laptop. Use any other value (`production`, `staging`, …) for deployed environments.
   - **`ALLOW_LOCAL_STUB_LOGIN`**: keep `false` except on your own machine. See below.
   - **`STUB_USERS_FILE`** (optional): path to the git-ignored stub passwords (default `local/stub-users.json`)

3. Do not commit `.env`. `.gitignore` ignores `.env` and `.env.*` and keeps `.env.example`.

The API exits on startup if `JWT_SECRET_KEY` is missing, shorter than 32 characters, or still the `.env.example` placeholder, and if `DATABASE_URL` is missing.

## Running the Application

### Dash Web Application

The main web interface defaults to http://127.0.0.1:8055. Debug mode is off unless `DASH_DEBUG=true`.

```bash
python app_dash_web.py
```

Then visit http://127.0.0.1:8055 in your browser.

Each screen has its own address, so refresh, back, and links stay on that screen:

| Screen | Address |
| --- | --- |
| Landing | `/` |
| Sign in | `/signin` |
| Get started | `/get-started` |
| Dashboard | `/dashboard` |
| My Ajo | `/circle` |
| Members | `/members` |
| Payouts Tracker (admin only) | `/payouts` |
| Financial Health Overview | `/credit` |
| Auto-loan | `/autoloan` |
| Wallet | `/wallet` |

Opening `/payouts` directly is sent to `/dashboard` unless the signed-in user is the creator of an Ajo. Someone who is not signed in and opens an app address is sent to `/signin`. The server decides that from the session; the address itself does not grant a role.

### Local stub sign-in

`admintest` (admin) and `membertest` (member) can sign in only on your machine. There is no role toggle. The server decides the role; the browser cannot switch it. Payouts Tracker is shown only to the creator of that Ajo. With these local accounts, that creator is `admintest`. `membertest` is redirected to the dashboard and does not see the PayoutsTracker menu.

1. Copy the password template and edit the copy. Do not commit it.
   ```bash
   cp local/stub-users.example.json local/stub-users.json
   ```
2. In `.env`, set:
   ```bash
   ALLOW_LOCAL_STUB_LOGIN=true
   DASH_HOST=127.0.0.1
   AJO_ENV=local
   ```
3. Start the Dash app and sign in with the username and the password from `local/stub-users.json`.

Startup refuses to continue if `ALLOW_LOCAL_STUB_LOGIN` is true while `DASH_HOST` is not `127.0.0.1`, `localhost`, or `::1`, or while `AJO_ENV` is anything other than unset or `local`. With the flag off, those accounts cannot sign in. Leave the flag false in every shared or deployed environment.

### Sign up, sign in, and settings

1. Start the Dash app with the stub sign-in settings above.
2. Open http://127.0.0.1:8055. The landing card is **Get started**.
3. **Get started** opens Registration: first name, last name, email, phone, set password, and confirm password. The card is the same width as the landing card. This form does not create a server account.
4. **I have an account** opens Sign in. Use `admintest` or `membertest` and the password in `local/stub-users.json`. There is no role toggle. The server session sets admin or member.
5. Under the username, **Settings** opens the settings page (also available from the top bar when the sidebar is hidden).
6. **Complete profile** starts due diligence. The UK credit check is the default path. The Nigeria step is locked, greyed out, and marked with a padlock, and it does not run.
7. **Verified - finish setup** returns to Settings. Address completion is saved for the current session only. Phone verification, password reset by email, and direct debit are shown and do not send SMS, email, or a payment instruction in this build.

### Join Ajo

After the stub sign-in above, open **+ Join Ajo** under **My circles** in the sidebar. The address is http://127.0.0.1:8055/join.

1. Search by circle name or city, then choose **Search** (or press Enter).
2. Filter by All groups, Active, Completed, Open to join, or Groups I manage.
3. Set a date range. A circle stays on the page when its start and end overlap that range.
4. On a card, **View details** opens the circle summary. **Join** sends a local join request when the circle is open and you are not already a member.
5. **Invite Member** opens the invitation dialog (email required, personal message optional). Nothing is emailed in this preview; the screen confirms the invitation was queued.
6. **Manage Members** is on the same button row only when the signed-in profile created that circle. `admintest` sees it on Brum Builders, Sister Circle Ajo, and Wolverhampton Sisters. `membertest` does not see it.

```bash
pytest tests/test_join.py -v
```

### FastAPI Backend

The FastAPI service is a separate process for authentication and API endpoints. Set `JWT_SECRET_KEY` and `DATABASE_URL` first (see above). Local development uses SQLite. The database file holds synthetic data only.

```bash
alembic upgrade head
uvicorn api:app --reload --no-proxy-headers
```

`alembic upgrade head` creates the tables. `uvicorn` runs the API on http://localhost:8000 by default. `--no-proxy-headers` is required so `X-Forwarded-For` and `Forwarded` cannot change the client address. `GET /health` checks that the database answers.

Sign-up, sign-in, refresh, logout, and sessions are under `/api/v1/auth/`. Sign-up always returns the same message, whether or not the email is already registered. Sign-in returns an access token (15 minutes) and a refresh token. Each refresh token is consumed by one conditional update, so a second use fails and ends that session. Emails are stored trimmed and lowercased. Logout revokes that session on the server. Rate limiting is not in this build: signup, login, and password reset call `enforce_auth_attempt_policy` in `auth.py`, which is the function a later rate-limit change should replace.

`SEED_DEMO_ACCOUNTS=true` creates only `admintest@example.test` and `membertest@example.test`, with passwords from the git-ignored stub credentials file. The process refuses to start if that flag is on while `AJO_ENV` is unset or is not `local` or `dev`. The ten demo personas stay display data and have no user rows.

`POST /api/v1/auth/password/forgot` always returns the same message. When `AJO_ENV` is `local` or `dev`, the reset link is written to the git-ignored `local/email-inbox` folder (and kept in memory for tests). It is not written to the application log. The link expires after 30 minutes, is consumed by one conditional update, and a successful reset ends every session. Audit rows store HMAC-SHA256 of the email under `AUDIT_EMAIL_HMAC_KEY` (or a git-ignored local key file). They do not store a plain SHA-256 of the address. Setting `EMAIL_SENDER=dev` when `AJO_ENV` is unset or anything other than `local` or `dev` makes the process refuse to start. Otherwise those environments return an error from the email endpoints until a real provider is configured.

Sign-up sends a verification link through that same inbox. The link expires after 24 hours and is consumed by one conditional update, so a second use fails. Unverified users can sign in. `POST /api/v1/circles` and `POST /api/v1/circles/{id}/join` reject them until they confirm. The Join Ajo page and the Create Ajo row show "Verify your email" when the session says the address is not verified. Seeded test users count as pre-verified unless a member sets `email_verified` to false. Resend calls `enforce_auth_attempt_policy` with action `resend_verification`.

CI runs the same migration and the same API tests against Postgres 16. A `postgresql://` URL uses the pinned psycopg2 driver. Moving to GCP Cloud SQL later is a configuration change: create a Postgres instance, set `DATABASE_URL` to its connection string (through the Cloud SQL Auth Proxy or a connector), and run `alembic upgrade head` again. Application code stays the same because the models use portable SQLAlchemy types. Money columns, when they are added, are integer pence.

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `JWT_SECRET_KEY` | Yes (API) | — | Secret for signing JWT tokens (minimum 32 characters; not the example placeholder) |
| `DATABASE_URL` | Yes (API) | — | `sqlite:///local/ajo.db` locally. A `postgresql://` URL in CI and on Cloud SQL |
| `ACCESS_TOKEN_MINUTES` | No | `15` | Access-token lifetime in minutes (capped at 60). `JWT_EXPIRY_DAYS` is ignored |
| `REFRESH_TOKEN_DAYS` | No | `14` | Opaque refresh-token lifetime in days. Stored as a SHA-256 hash and rotated on use |
| `DASH_DEBUG` | No | `false` | Enable Dash debug mode (local development only) |
| `DASH_HOST` | No | `127.0.0.1` | Dash server host. Must be `127.0.0.1`, `localhost`, or `::1` when stub sign-in is enabled |
| `DASH_PORT` | No | `8055` | Dash server port |
| `AJO_ENV` | No | unset | `local` (or unset) for a laptop. Any other value is a non-local environment |
| `ALLOW_LOCAL_STUB_LOGIN` | No | `false` | Enable `admintest` / `membertest` sign-in. Local loopback only; otherwise the process exits |
| `STUB_USERS_FILE` | No | `local/stub-users.json` | Git-ignored JSON file with stub passwords |
| `ALLOW_TEST_CLOCK` | No | `false` | Let tests or a loopback dev process move the clock. Any other process exits on startup |
| `SEED_DEMO_ACCOUNTS` | No | `false` | Seed `admintest` and `membertest` API users. Refused unless `AJO_ENV` is `local` or `dev` |

## Security notes

- The API fails fast if a required secret is missing or the JWT secret is too short or still the example placeholder. There is no insecure fallback.
- Debug mode is disabled by default. Enable it only with `DASH_DEBUG=true`.
- Stub sign-in is off unless `ALLOW_LOCAL_STUB_LOGIN=true`, and that setting is refused unless the app is bound to loopback in a local environment. Passwords are not committed; use `local/stub-users.example.json` as the template.
- The test clock stays on the wall clock unless `ALLOW_TEST_CLOCK=true`. That flag is refused outside the test suite and a loopback process with `AJO_ENV=local` or `AJO_ENV=dev`. Production and staging cannot move time.
- Demo seeding stays off unless `SEED_DEMO_ACCOUNTS=true`. That flag is refused when `AJO_ENV` is unset or is not `local` or `dev`. It never creates the ten demo personas.
- Generate a new JWT secret for every environment. Never reuse the value in `.env.example`.

## Development

### Running Tests

```bash
pytest tests/
```

API checks (health and auth) are in `tests/test_api.py`. Session, refresh, and sign-in checks are in `tests/test_auth_sessions.py`. They use SQLite unless `DATABASE_URL` already points at Postgres. Startup checks for the JWT secret are in `tests/test_api_startup.py`. Local stub sign-in checks are in `tests/test_stub_login.py`. The test clock and dev-only control are in `tests/test_clock.py`. Seeded-circle checks are in `tests/test_clock_seeded_circles.py`. Persona fixture checks are in `tests/test_personas.py`. Dummy-circle creator checks are in `tests/test_circles.py`. My Ajo checks are in `tests/test_my_ajo.py`. Page-address checks are in `tests/test_page_routes.py`. Role visibility checks (what `admintest` and `membertest` can see, including Payouts Tracker, a typed `/payouts` address, and the signed-in `/settings` gate) are in `tests/test_role_visibility.py`. Dashboard checks are in `tests/test_dashboard.py`. Sidebar circle checks are in `tests/test_my_circles.py`. Members page checks are in `tests/test_members.py`. Join Ajo checks are in `tests/test_join.py`. Wallet checks are in `tests/test_wallet.py`. FinHealth checks are in `tests/test_finhealth.py`.

```bash
pytest tests/test_role_visibility.py tests/test_dashboard.py tests/test_my_circles.py tests/test_join.py tests/test_finhealth.py -v
```

### Financial Health Overview

Sign in with a local stub account, then choose **FinHealth** in the sidebar. The page title and breadcrumb are **Financial Health Overview**. The address is `/credit`.

- The country-of-origin card is greyed out and locked. It cannot be clicked.
- **Affordability Assessment** shows tuition £14000, bank balance £16258, threshold met, and cross-border debt £0. The chart switches between 12-month financial history and a 7-day volatility check.
- **Affordability Forecast** shows tuition £14000.00, a 30th-day forecast of £17950.00, a buffer of £3950.00, and a 50-90% probability. The chart switches between the next 30 days and forecast versus validation data.

### Test clock

`clock.now()` is the time provider. Access tokens use it for expiry (15 minutes by default). Tests call `freeze`, `advance`, and `reset`. On a laptop you can also move the running API with `ALLOW_TEST_CLOCK=true`, `AJO_ENV=local` (or `dev`), and `DASH_HOST` set to `127.0.0.1`, `localhost`, or `::1`:

- `GET /api/v1/dev/clock` reads the current time.
- `POST /api/v1/dev/clock` sends exactly one of `advance_seconds`, `freeze_at` (ISO-8601), or `reset`.

Each of those requests returns 404 unless `request.client.host` is `127.0.0.1` or `::1`. `DASH_HOST`, the uvicorn `--host` setting, `X-Forwarded-For`, and `Forwarded` do not count. Start the API with `--no-proxy-headers`.

The route is not registered otherwise. If the flag is on in production, staging, or any other deploy, the API and the Dash app exit at startup. Production always reads the wall clock.

### Seeded test circles

`data/seeded_circles.json` is the committed seed for tests. Names are obviously fake (`Testperson`, `Sampledata`, `Faketest`, and the same kind of marker). Emails are `@example.test`. The file has no passwords and no bank details. `seeded_circles.load_seeded_circles()` rejects a real-looking name, a non-example email, a sort code, an account number, an IBAN, or a card number.

```bash
pytest tests/test_clock.py tests/test_clock_seeded_circles.py -v
```

### Dummy personas

Ten synthetic personas (names, dummy `@example.test` emails, and simple passwords) are the local test set for later UI work. They are not real people and include no phone numbers, addresses, or bank details.

Five are members of both Brum Builders and Sister Circle Ajo. Five are members of only one of those groups. One persona is the admin who created both groups.

My Ajo uses that file. `admintest` is shown as Amina Testperson and switches between Brum Builders and Sister Circle Ajo with the same group tabs as Payouts Tracker. `membertest` is shown as Tunde Exampleonly and sees only Brum Builders. The screen is the original rotation timeline, circle rules, and contribution progress for the selected Ajo. The signed-in person is tagged "you". Emails and passwords are not shown.

The live file is git-ignored. Copy the committed template once:

```bash
cp data/personas.example.json data/personas.json
```

Load it from Python:

```bash
python -c "from pages.personas import load_personas; print(len(load_personas()['personas']))"
```

The My Ajo page reads `data/personas.json` when the copy exists, and otherwise the example template. Persona passwords are not shown. Open My Ajo after the local stub sign-in above. Amina's two groups are tabs. Tunde's sign-in shows only Brum Builders.

Run the persona tests:

```bash
pytest tests/test_personas.py -v
```

### Sidebar My circles

The signed-in sidebar reads its circle list and the Create circle / Join Ajo rows from dummy data.

- Circle names are the signed-in persona's groups from the persona fixture, in file order. `admintest` sees both groups. `membertest` sees Brum Builders only. The app reads `data/personas.json` when that file exists, and otherwise `data/personas.example.json`.
- Create circle and Join Ajo (Join Ajo directly under Create circle) are the two rows in `data/circle_actions.json`.

Both files are temporary stand-ins until circles are stored in the database. Payouts Tracker stays limited to the creator of that Ajo. With the local stub accounts, that creator is `admintest`.

```bash
pytest tests/test_my_circles.py -v
```

## Project Structure

- `app_dash_web.py` - Main Dash web application
- `api.py` - FastAPI backend service (authentication, API endpoints)
- `database.py` - SQLAlchemy engine, session, and models (SQLite and PostgreSQL)
- `alembic.ini`, `migrations/` - schema migrations (`alembic upgrade head`)
- `tests/` - Test suite, including the FastAPI health and auth checks
- `pages/` - Dash page components and layouts
- `.env.example` - Placeholder environment variables (no real secrets)
- `requirements.txt` - Production dependencies (pinned versions)
- `requirements-dev.txt` - Development and testing dependencies
