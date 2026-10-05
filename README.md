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

3. Do not commit `.env`. `.gitignore` ignores `.env` and `.env.*` and keeps `.env.example`.

The API exits on startup if `JWT_SECRET_KEY` is missing, shorter than 32 characters, or still the `.env.example` placeholder, and if `DATABASE_URL` is missing.

## Running the Application

### Dash Web Application

The main web interface defaults to http://127.0.0.1:8055. Debug mode is off unless `DASH_DEBUG=true`.

```bash
python app_dash_web.py
```

Then visit http://127.0.0.1:8055 in your browser.

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
| `DASH_HOST` | No | `127.0.0.1` | Dash server host |
| `DASH_PORT` | No | `8055` | Dash server port |

## Security notes

- The API fails fast if a required secret is missing or the JWT secret is too short or still the example placeholder. There is no insecure fallback.
- Debug mode is disabled by default. Enable it only with `DASH_DEBUG=true`.
- Generate a new JWT secret for every environment. Never reuse the value in `.env.example`.

## Development

### Running Tests

```bash
pytest
```

Startup checks for the JWT secret are in `test_api_startup.py`. Persona fixture checks are in `test_personas.py`.

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
