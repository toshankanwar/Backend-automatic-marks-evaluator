from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId
from datetime import datetime, timezone, timedelta
import secrets
import hashlib

from app.core.database import db
from app.core.security import hash_password, verify_password, create_access_token
from app.core.config import settings
from app.deps.auth_deps import get_current_user
from app.schemas.auth_schema import (
    SignupRequest,
    LoginRequest,
    AuthResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from app.services.email_service import (
    send_welcome_email,
    send_reset_password_email,
    send_password_changed_email,
)
def _to_utc(dt: datetime) -> datetime:
    """Normalize datetime to timezone-aware UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

router = APIRouter(prefix="/auth", tags=["Auth"])


def _hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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

    # Do not fail signup if email sending fails
    try:
        send_welcome_email(to_email=doc["email"], user_name=doc["name"])
    except Exception as e:
        print(f"[auth.signup] Welcome email failed for {doc['email']}: {e}")

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


@router.post("/change-password")
async def change_password(payload: ChangePasswordRequest, current_user=Depends(get_current_user)):
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="New password and confirm password do not match")

    if payload.old_password == payload.new_password:
        raise HTTPException(status_code=400, detail="New password must be different from old password")

    user = await db.users.find_one({"_id": ObjectId(current_user["sub"])})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(payload.old_password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Old password is incorrect")

    await db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "password_hash": hash_password(payload.new_password),
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )

    try:
        send_password_changed_email(to_email=user["email"], user_name=user.get("name", "there"))
    except Exception as e:
        print(f"[auth.change-password] mail failed: {e}")

    return {"message": "Password changed successfully"}


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest):
    # Security: avoid user enumeration
    generic_response = {"message": "If this email is registered, reset instructions have been sent."}

    user = await db.users.find_one({"email": payload.email.lower()})
    if not user:
        return generic_response

    raw_token = secrets.token_urlsafe(48)
    token_hash = _hash_reset_token(raw_token)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=getattr(settings, "RESET_TOKEN_EXPIRE_MINUTES", 15))

    # Invalidate old unused tokens for this user
    await db.password_resets.update_many(
        {"user_id": str(user["_id"]), "used": False},
        {"$set": {"used": True, "invalidated_at": now}},
    )

    await db.password_resets.insert_one(
        {
            "user_id": str(user["_id"]),
            "token_hash": token_hash,
            "used": False,
            "created_at": now,
            "expires_at": expires_at,
        }
    )

    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"

    try:
        send_reset_password_email(
            to_email=user["email"],
            user_name=user.get("name", "there"),
            reset_link=reset_link,
            expiry_minutes=settings.RESET_TOKEN_EXPIRE_MINUTES,
        )
    except Exception as e:
        print(f"[auth.forgot-password] mail failed: {e}")

    return generic_response


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest):
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="New password and confirm password do not match")

    token_hash = _hash_reset_token(payload.token)
    rec = await db.password_resets.find_one({"token_hash": token_hash, "used": False})

    if not rec:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    now_utc = datetime.now(timezone.utc)
    expires_at_utc = _to_utc(rec["expires_at"])

    # Expired token => mark used/invalid and reject
    if expires_at_utc < now_utc:
        await db.password_resets.update_one(
            {"_id": rec["_id"]},
            {"$set": {"used": True, "invalidated_at": now_utc}},
        )
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    # Validate user id safely
    try:
        user_obj_id = ObjectId(rec["user_id"])
    except Exception:
        await db.password_resets.update_one(
            {"_id": rec["_id"]},
            {"$set": {"used": True, "invalidated_at": now_utc}},
        )
        raise HTTPException(status_code=400, detail="Invalid reset token user reference")

    user = await db.users.find_one({"_id": user_obj_id})
    if not user:
        await db.password_resets.update_one(
            {"_id": rec["_id"]},
            {"$set": {"used": True, "invalidated_at": now_utc}},
        )
        raise HTTPException(status_code=404, detail="User not found")

    if verify_password(payload.new_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="New password must be different from old password")

    # Update password
    await db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "password_hash": hash_password(payload.new_password),
                "updated_at": now_utc,
            }
        },
    )

    # Mark this token used
    await db.password_resets.update_one(
        {"_id": rec["_id"]},
        {"$set": {"used": True, "used_at": now_utc}},
    )

    # Optional hardening: invalidate all other active reset tokens for same user
    await db.password_resets.update_many(
        {
            "user_id": str(user["_id"]),
            "used": False,
            "_id": {"$ne": rec["_id"]},
        },
        {"$set": {"used": True, "invalidated_at": now_utc}},
    )

    try:
        send_password_changed_email(
            to_email=user["email"],
            user_name=user.get("name", "there"),
        )
    except Exception as e:
        print(f"[auth.reset-password] mail failed: {e}")

    return {"message": "Password reset successful"}