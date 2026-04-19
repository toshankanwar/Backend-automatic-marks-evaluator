from datetime import datetime, timezone
from fastapi import APIRouter, Header, HTTPException
from app.core.database import db
from app.core.config import settings

router = APIRouter(prefix="/maintenance", tags=["Maintenance"])


@router.get("/cleanup-password-resets")
async def cleanup_password_resets(x_cron_secret: str = Header(default="")):
    # security check
    if not settings.CRON_SECRET or x_cron_secret != settings.CRON_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    now = datetime.now(timezone.utc)

    result = await db.password_resets.delete_many({
        "$or": [
            {"used": True},
            {"expires_at": {"$lt": now}},
        ]
    })

    return {
        "ok": True,
        "deleted_count": result.deleted_count,
        "ran_at": now.isoformat()
    }