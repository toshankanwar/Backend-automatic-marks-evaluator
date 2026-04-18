from fastapi import APIRouter, HTTPException
from app.core.database import db
from app.core.security import hash_password, verify_password, create_access_token
from app.schemas.auth_schema import SignupRequest, LoginRequest, AuthResponse
from datetime import datetime, timezone

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/signup", response_model=AuthResponse)
async def signup(payload: SignupRequest):
    existing = await db.users.find_one({"email": payload.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    now = datetime.now(timezone.utc)
    doc = {
        "name": payload.name.strip(),
        "email": payload.email.lower(),
        "password_hash": hash_password(payload.password),
        "created_at": now,
        "updated_at": now,
    }
    result = await db.users.insert_one(doc)
    user_id = str(result.inserted_id)

    token = create_access_token({"sub": user_id, "email": doc["email"], "name": doc["name"]})
    return AuthResponse(
        user_id=user_id,
        name=doc["name"],
        email=doc["email"],
        access_token=token,
    )

@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest):
    user = await db.users.find_one({"email": payload.email.lower()})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user_id = str(user["_id"])
    token = create_access_token({"sub": user_id, "email": user["email"], "name": user["name"]})
    return AuthResponse(
        user_id=user_id,
        name=user["name"],
        email=user["email"],
        access_token=token,
    )