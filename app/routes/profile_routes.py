from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId
from datetime import datetime, timezone

from app.core.database import db
from app.core.security import verify_password
from app.schemas.auth_schema import (
    ProfileResponse,
    UpdateProfileRequest,
    DeleteAccountRequest,
)
from app.services.email_service import send_account_deleted_email
from app.deps.auth_deps import get_current_user  # ✅ use your actual dependency file path

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("/me", response_model=ProfileResponse)
async def get_profile(current_user=Depends(get_current_user)):
    user = await db.users.find_one({"_id": ObjectId(current_user["sub"])})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return ProfileResponse(
        user_id=str(user["_id"]),
        name=user["name"],
        email=user["email"],
        created_at=user.get("created_at").isoformat() if user.get("created_at") else None,
    )


@router.put("/me", response_model=ProfileResponse)
async def update_profile(payload: UpdateProfileRequest, current_user=Depends(get_current_user)):
    uid = ObjectId(current_user["sub"])
    await db.users.update_one(
        {"_id": uid},
        {"$set": {"name": payload.name.strip(), "updated_at": datetime.now(timezone.utc)}},
    )
    user = await db.users.find_one({"_id": uid})
    return ProfileResponse(
        user_id=str(user["_id"]),
        name=user["name"],
        email=user["email"],
        created_at=user.get("created_at").isoformat() if user.get("created_at") else None,
    )


@router.delete("/me")
async def delete_account(payload: DeleteAccountRequest, current_user=Depends(get_current_user)):
    if payload.confirm_text != "DELETE":
        raise HTTPException(status_code=400, detail='confirm_text must be "DELETE"')

    uid = ObjectId(current_user["sub"])
    user = await db.users.find_one({"_id": uid})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid password")

    user_id_str = str(uid)

    # delete related data
    await db.evaluations.delete_many({"user_id": user_id_str})
    await db.results.delete_many({"user_id": user_id_str})
    await db.ocr_accuracy_results.delete_many({"user_id": user_id_str})  # ✅ add this collection
    # if your collection name is different, use that exact name (e.g., db.ocr_accuracy or db.ocr_results)

    await db.users.delete_one({"_id": uid})

    try:
        send_account_deleted_email(user["email"], user.get("name", "User"))
    except Exception as e:
        print(f"[profile.delete_account] mail failed: {e}")

    return {"message": "Account and related data deleted successfully"}