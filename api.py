"""
api.py  —  Ajo FastAPI backend
-------------------------------
This is a SEPARATE Python process from your Dash app.
Run it alongside Dash:

  Terminal 1:  python app.py          (Dash, port 8050)
  Terminal 2:  uvicorn api:app        (FastAPI, port 8000)

Install dependencies:
  pip install fastapi uvicorn sqlalchemy psycopg2-binary passlib[bcrypt] python-jose
"""

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext  # for hashing passwords
from sqlalchemy.orm import Session
from database import get_db, User         # we'll create database.py next

app = FastAPI(title="Ajo API", version="1.0.0")

# ─── Password hashing ─────────────────────────────────────────────────────────
#
#  NEVER store plain-text passwords.
#  passlib hashes them with bcrypt — a slow, secure algorithm.
#
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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

from jose import jwt
from datetime import datetime, timedelta

SECRET_KEY = "change-this-to-a-long-random-string-in-production"
ALGORITHM = "HS256"

def create_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(days=30),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


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

    # ── Step 3: Hash the password
    hashed_password = pwd_context.hash(body.password)
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
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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