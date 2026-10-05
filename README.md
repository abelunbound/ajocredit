# AjoFinance

A community finance platform built with Plotly Dash and FastAPI.

## Prerequisites

- Python 3.12+
- PostgreSQL (for the FastAPI backend)

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
   - **`DATABASE_URL`** (required by the API): PostgreSQL connection string, `postgresql://username:password@host:port/database`
   - **`JWT_EXPIRY_DAYS`** (optional): JWT lifetime in days (default `30`)
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

### Local stub sign-in

`admintest` (admin) and `membertest` (member) can sign in only on your machine. There is no role toggle. The server decides the role; the browser cannot switch it. Payouts Tracker is shown only for `admintest`.

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

### FastAPI Backend

The FastAPI service is a separate process for authentication and API endpoints. Set `JWT_SECRET_KEY` and `DATABASE_URL` first (see above). `database.py` is not in this milestone; the process still requires those environment variables before it imports the database module.

```bash
uvicorn api:app --reload
```

This runs on http://localhost:8000 by default.

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `JWT_SECRET_KEY` | Yes (API) | — | Secret for signing JWT tokens (minimum 32 characters; not the example placeholder) |
| `DATABASE_URL` | Yes (API) | — | PostgreSQL connection string |
| `JWT_EXPIRY_DAYS` | No | `30` | JWT token expiration in days |
| `DASH_DEBUG` | No | `false` | Enable Dash debug mode (local development only) |
| `DASH_HOST` | No | `127.0.0.1` | Dash server host. Must be `127.0.0.1`, `localhost`, or `::1` when stub sign-in is enabled |
| `DASH_PORT` | No | `8055` | Dash server port |
| `AJO_ENV` | No | unset | `local` (or unset) for a laptop. Any other value is a non-local environment |
| `ALLOW_LOCAL_STUB_LOGIN` | No | `false` | Enable `admintest` / `membertest` sign-in. Local loopback only; otherwise the process exits |
| `STUB_USERS_FILE` | No | `local/stub-users.json` | Git-ignored JSON file with stub passwords |

## Security notes

- The API fails fast if a required secret is missing or the JWT secret is too short or still the example placeholder. There is no insecure fallback.
- Debug mode is disabled by default. Enable it only with `DASH_DEBUG=true`.
- Stub sign-in is off unless `ALLOW_LOCAL_STUB_LOGIN=true`, and that setting is refused unless the app is bound to loopback in a local environment. Passwords are not committed; use `local/stub-users.example.json` as the template.
- Generate a new JWT secret for every environment. Never reuse the value in `.env.example`.

## Development

### Running Tests

```bash
pytest
```

Startup checks for the JWT secret are in `test_api_startup.py`. Local stub sign-in checks are in `test_stub_login.py`. Persona fixture checks are in `test_personas.py`. Dummy-circle creator checks are in `test_circles.py`.

### Dummy personas

Ten synthetic personas (names, dummy `@example.test` emails, and simple passwords) are the local test set for later UI work. They are not real people and include no phone numbers, addresses, or bank details.

Five are members of both Brum Builders and Sister Circle Ajo. Five are members of only one of those groups. One persona is the admin who created both groups.

The live file is git-ignored. Copy the committed template once:

```bash
cp data/personas.example.json data/personas.json
```

Load it from Python:

```bash
python -c "from pages.personas import load_personas; print(len(load_personas()['personas']))"
```

The My Ajo page treats those groups as dummy circles. Each circle records `created_by`, and that persona is the admin of the Ajo. The page reads `data/personas.json` when the copy exists, and otherwise the example template. Persona passwords are not shown. Open My Ajo after the local stub sign-in above to see the creator on Brum Builders and Sister Circle Ajo.

Run the persona tests:

```bash
pytest test_personas.py -v
```

## Project Structure

- `app_dash_web.py` - Main Dash web application
- `api.py` - FastAPI backend service (authentication, API endpoints)
- `pages/` - Dash page components and layouts
- `.env.example` - Placeholder environment variables (no real secrets)
- `requirements.txt` - Production dependencies (pinned versions)
- `requirements-dev.txt` - Development and testing dependencies
