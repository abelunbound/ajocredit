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

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = int(os.getenv("JWT_EXPIRY_DAYS", "30"))

import bcrypt
from fastapi import FastAPI, HTTPException, Depends, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import text
from sqlalchemy.orm import Session
from database import get_db, User

app = FastAPI(title="Ajo API", version="1.0.0")

# bcrypt (the maintained PyCA library) hashes passwords. passlib is not used.
BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


# ─── Request / Response models ────────────────────────────────────────────────
#
#  Pydantic models define exactly what shape of data this route accepts.
#  FastAPI auto-validates incoming JSON against these — if the email is
#  malformed or a field is missing, it returns a 422 automatically.
#
class SignupRequest(BaseModel):
    name: str
    email: EmailStr          # Pydantic validates email format for free
    password: str

class SignupResponse(BaseModel):
    user_id: int
    name: str
    email: str
    token: str               # JWT token the frontend stores for future requests


# ─── Helper: generate JWT token ───────────────────────────────────────────────

import jwt
from datetime import datetime, timedelta, timezone

def create_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": clock_now() + timedelta(days=JWT_EXPIRY_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


# ─── POST /api/v1/auth/signup ─────────────────────────────────────────────────
#
#  This is the route your Dash app calls from the callback.
#
#  What it does, step by step:
#    1. Receives the JSON body (name, email, password)
#    2. Pydantic validates the shape automatically
#    3. We check the database — is this email already registered?
#    4. Hash the password (NEVER store it plain)
#    5. Save the new user to the database
#    6. Return a JWT token so the frontend can stay logged in
#
@app.post(
    "/api/v1/auth/signup",
    response_model=SignupResponse,
    status_code=201,               # 201 = Created (not 200 = OK)
)
def signup(body: SignupRequest, db: Session = Depends(get_db)):

    # ── Step 1: Check if email already exists
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(
            status_code=409,                                # 409 Conflict
            detail="An account with this email already exists."
        )

    # ── Step 2: Validate password length
    if len(body.password) < 8:
        raise HTTPException(
            status_code=422,
            detail="Password must be at least 8 characters."
        )
    if len(body.password.encode("utf-8")) > BCRYPT_MAX_BYTES:
        raise HTTPException(
            status_code=422,
            detail="Password must be at most 72 bytes."
        )

    # ── Step 3: Hash the password
    hashed_password = hash_password(body.password)
    # hashed_password looks like: "$2b$12$KIXmFgp3..." — safe to store

    # ── Step 4: Save user to database
    new_user = User(
        name=body.name,
        email=body.email,
        hashed_password=hashed_password,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)          # get the auto-generated user_id back

    # ── Step 5: Create a JWT token
    token = create_token(new_user.id)

    # ── Step 6: Return the response
    #    Dash callback receives this as response.json()
    return SignupResponse(
        user_id=new_user.id,
        name=new_user.name,
        email=new_user.email,
        token=token,
    )


# ─── GET /api/v1/me  (example of a protected route) ──────────────────────────
#
#  Once the user is logged in, Dash sends the token in the
#  Authorization header on every future request:
#
#    headers={"Authorization": f"Bearer {token}"}
#
#  The backend verifies the token and returns the user's data.

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

bearer = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return user

@app.get("/api/v1/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "user_id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
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