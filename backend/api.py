"""
backend/api.py  —  Ajo FastAPI backend
--------------------------------------
This is a separate Python process from the Dash app.
From the repository root, one command starts both (API 8000, Dash 8055):

  ./utils/dev-launch-local.sh

That script runs:

  uvicorn backend.api:app --reload --no-proxy-headers
  python frontend/app_dash_web.py

Install dependencies:
  pip install -r requirements.txt

Local database (synthetic data only). The SQLite path is relative to the
repository root, and local/ajo.db is git-ignored:
  DATABASE_URL=sqlite:///local/ajo.db alembic upgrade head
"""

import os
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

# Same file Dash loads. Skip under pytest so startup-failure tests still see
# a missing or placeholder secret instead of values from a local .env.
if not os.environ.get("PYTEST_CURRENT_TEST"):
    load_dotenv(override=False)

# ─── Configuration: Load from environment ─────────────────────────────────────
#
#  Validate secrets before importing the rest of the app. A bad secret must
#  fail before backend.database is imported.
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
from backend.stub_auth import enforce_local_stub_policy

enforce_local_stub_policy()

from backend.clock import (  # noqa: E402
    ClockLocked,
    advance as clock_advance,
    dev_control_allowed,
    enforce_test_clock_policy,
    freeze as clock_freeze,
    now as clock_now,
    reset as clock_reset,
)

enforce_test_clock_policy()

from backend.demo_accounts import enforce_demo_seed_policy, seed_demo_accounts  # noqa: E402
from backend.mail import enforce_dev_email_policy  # noqa: E402

enforce_demo_seed_policy()
enforce_dev_email_policy()

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.auth import (
    access_token_minutes,
    create_access_token as _create_access_token,
    register_auth_routes,
)
from backend.circles import register_circle_routes
from backend.database import User, get_db
from backend.email_verification import register_email_verification_routes
from backend.password_reset import register_password_reset_routes
from backend.roles import register_role_routes
import backend.audit as audit
from backend.audit import register_audit_routes
from backend.ledger_admin import register_ledger_admin_routes

JWT_ALGORITHM = "HS256"
# Swagger, ReDoc, and the OpenAPI document. Any other AJO_ENV, including unset, hides them.
_OPENAPI_ENVS = frozenset({"local", "dev"})


def openapi_docs_enabled() -> bool:
    """True only when AJO_ENV is local or dev, ignoring case and surrounding space."""
    raw = os.getenv("AJO_ENV")
    if raw is None:
        return False
    return raw.strip().lower() in _OPENAPI_ENVS


def create_access_token(user_id: int, session_id: int) -> str:
    """Access token whose expiry is ``clock.now()`` plus ``access_token_minutes()``."""
    return _create_access_token(user_id, session_id, secret=JWT_SECRET_KEY)


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


def create_app() -> FastAPI:
    """Build the API. Interactive docs exist only for local and dev."""
    if openapi_docs_enabled():
        docs_url: str | None = "/docs"
        redoc_url: str | None = "/redoc"
        openapi_url: str | None = "/openapi.json"
    else:
        docs_url = None
        redoc_url = None
        openapi_url = None
    application = FastAPI(
        title="Ajo API",
        version="1.0.0",
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )
    get_current_user = register_auth_routes(application, jwt_secret=JWT_SECRET_KEY)
    seed_demo_accounts()
    register_password_reset_routes(application)
    register_email_verification_routes(application)
    register_circle_routes(application, get_current_user)
    register_role_routes(application, get_current_user)
    register_audit_routes(application, get_current_user)
    register_ledger_admin_routes(application, get_current_user)

    @application.middleware("http")
    async def bind_audit_request(request: Request, call_next):
        """Expose the request to the audit log. The client IP is the TCP peer."""
        token = audit.bind_request(request)
        try:
            return await call_next(request)
        finally:
            audit.reset_request(token)

    @application.exception_handler(RequestValidationError)
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

    @application.get("/health")
    def health(db: Session = Depends(get_db)):
        db.execute(text("SELECT 1"))
        return {"status": "ok"}

    # ─── GET /api/v1/me  (protected route) ────────────────────────────────────
    #
    #  Authorization: Bearer <access token>
    #  The access token is a short-lived PyJWT. The server also checks that the
    #  session id inside it is still active, so logout works before the token expires.

    @application.get("/api/v1/me")
    def get_me(current_user: User = Depends(get_current_user)):
        return {
            "user_id": current_user.id,
            "name": current_user.name,
            "email": current_user.email,
            "email_verified": current_user.email_verified_at is not None,
        }

    if dev_control_allowed():
        register_dev_clock_routes(application)
    return application


app = create_app()