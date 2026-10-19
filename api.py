"""
api.py  —  Ajo FastAPI backend
-------------------------------
This is a SEPARATE Python process from your Dash app.
Run it alongside Dash:

  Terminal 1:  python app.py          (Dash, port 8050)
  Terminal 2:  uvicorn api:app --no-proxy-headers        (FastAPI, port 8000)

Install dependencies:
  pip install -r requirements.txt

Local database (synthetic data only):
  DATABASE_URL=sqlite:///local/ajo.db alembic upgrade head
  uvicorn api:app --no-proxy-headers
"""

import os
import sys
from datetime import datetime, timedelta, timezone

# ─── Configuration: Load from environment ─────────────────────────────────────
#
#  Validate secrets before importing the rest of the app. A bad secret must
#  fail before database.py is imported.
#
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
INSECURE_PLACEHOLDER = "your-super-secret-jwt-key-change-this-to-something-random-and-secure"

if not JWT_SECRET_KEY:
    print("ERROR: JWT_SECRET_KEY environment variable is required but not set.", file=sys.stderr)
    print("Please set JWT_SECRET_KEY to a secure random string (at least 32 characters).", file=sys.stderr)
    print("Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\"", file=sys.stderr)
    sys.exit(1)

if len(JWT_SECRET_KEY) < 32:
    print(f"ERROR: JWT_SECRET_KEY must be at least 32 characters long (got {len(JWT_SECRET_KEY)}).", file=sys.stderr)
    print("Generate a secure key with: python -c \"import secrets; print(secrets.token_urlsafe(32))\"", file=sys.stderr)
    sys.exit(1)

if JWT_SECRET_KEY == INSECURE_PLACEHOLDER:
    print("ERROR: JWT_SECRET_KEY is set to the insecure placeholder value from .env.example.", file=sys.stderr)
    print("NEVER use the example placeholder in production!", file=sys.stderr)
    print("Generate a secure key with: python -c \"import secrets; print(secrets.token_urlsafe(32))\"", file=sys.stderr)
    sys.exit(1)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable is required but not set.", file=sys.stderr)
    print("Please set DATABASE_URL to your database connection string.", file=sys.stderr)
    sys.exit(1)

# The Dash stub sign-in flag must not be enabled in a non-local environment,
# including when only this API process is started.
from stub_auth import enforce_local_stub_policy

enforce_local_stub_policy()

from clock import (  # noqa: E402
    ClockLocked,
    advance as clock_advance,
    dev_control_allowed,
    enforce_test_clock_policy,
    freeze as clock_freeze,
    now as clock_now,
    reset as clock_reset,
)

enforce_test_clock_policy()

from demo_accounts import enforce_demo_seed_policy, seed_demo_accounts  # noqa: E402
from mail import enforce_dev_email_policy  # noqa: E402

enforce_demo_seed_policy()
enforce_dev_email_policy()

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from auth import (
    access_token_minutes,
    create_access_token as _create_access_token,
    register_auth_routes,
)
from circles import register_circle_routes
from database import User, get_db
from email_verification import register_email_verification_routes
from password_reset import register_password_reset_routes
from roles import register_role_routes
import audit
from audit import register_audit_routes

JWT_ALGORITHM = "HS256"

app = FastAPI(title="Ajo API", version="1.0.0")
get_current_user = register_auth_routes(app, jwt_secret=JWT_SECRET_KEY)
seed_demo_accounts()
register_password_reset_routes(app)
register_email_verification_routes(app)
register_circle_routes(app, get_current_user)
register_role_routes(app, get_current_user)
register_audit_routes(app, get_current_user)


@app.middleware("http")
async def bind_audit_request(request: Request, call_next):
    """Expose the request to the audit log. The client IP is the TCP peer."""
    token = audit.bind_request(request)
    try:
        return await call_next(request)
    finally:
        audit.reset_request(token)


def create_access_token(user_id: int, session_id: int) -> str:
    """Access token whose expiry is ``clock.now()`` plus ``access_token_minutes()``."""
    return _create_access_token(user_id, session_id, secret=JWT_SECRET_KEY)


@app.exception_handler(RequestValidationError)
async def hide_secrets_in_validation_errors(_request: Request, exc: RequestValidationError):
    """Drop submitted values. A 422 must not echo a password."""
    cleaned = []
    for error in exc.errors():
        item = {}
        for key, value in error.items():
            if key == "input":
                continue
            if key == "ctx":
                item[key] = {name: str(ctx_value) for name, ctx_value in value.items()}
                continue
            item[key] = value
        cleaned.append(item)
    return JSONResponse(status_code=422, content={"detail": cleaned})


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


# ─── GET /api/v1/me  (protected route) ────────────────────────────────────────
#
#  Authorization: Bearer <access token>
#  The access token is a short-lived PyJWT. The server also checks that the
#  session id inside it is still active, so logout works before the token expires.

@app.get("/api/v1/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "user_id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "email_verified": current_user.email_verified_at is not None,
    }


class DevClockRequest(BaseModel):
    advance_seconds: int | None = None
    freeze_at: str | None = None
    reset: bool = False


# Only the TCP peer counts. X-Forwarded-For and Forwarded are never read.
# Uvicorn must be started with --no-proxy-headers so those headers cannot
# rewrite request.client.host before this check runs.
DEV_CLOCK_CLIENT_HOSTS = frozenset({"127.0.0.1", "::1"})


def require_dev_clock_client(request: Request) -> None:
    """404 unless this request's client address is loopback."""
    host = request.client.host if request.client is not None else ""
    if host not in DEV_CLOCK_CLIENT_HOSTS:
        raise HTTPException(status_code=404, detail="Not Found")


def register_dev_clock_routes(fastapi_app: FastAPI) -> None:
    """Mount the dev-only clock control. Refused unless local loopback allows it."""
    if not dev_control_allowed():
        raise ClockLocked(
            "The dev clock control is only available when ALLOW_TEST_CLOCK is set "
            "on a loopback process with AJO_ENV=local or AJO_ENV=dev."
        )

    @fastapi_app.get("/api/v1/dev/clock")
    def read_dev_clock(_client: None = Depends(require_dev_clock_client)):
        return {"now": clock_now().isoformat()}

    @fastapi_app.post("/api/v1/dev/clock")
    def update_dev_clock(body: DevClockRequest, _client: None = Depends(require_dev_clock_client)):
        chosen = sum(
            (
                body.advance_seconds is not None,
                body.freeze_at is not None,
                body.reset,
            )
        )
        if chosen != 1:
            raise HTTPException(
                status_code=422,
                detail="Send exactly one of advance_seconds, freeze_at, or reset.",
            )
        if body.reset:
            clock_reset()
        elif body.advance_seconds is not None:
            try:
                clock_advance(timedelta(seconds=body.advance_seconds))
            except OverflowError as exc:
                raise HTTPException(status_code=422, detail="advance_seconds is out of range.") from exc
        else:
            try:
                moment = datetime.fromisoformat(body.freeze_at.replace("Z", "+00:00"))
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="freeze_at must be an ISO-8601 datetime.") from exc
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=timezone.utc)
            clock_freeze(moment)
        return {"now": clock_now().isoformat()}


if dev_control_allowed():
    register_dev_clock_routes(app)