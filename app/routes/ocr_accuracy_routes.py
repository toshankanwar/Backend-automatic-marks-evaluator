from datetime import datetime, timezone
import re

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException

from app.services.ocr_service import extract_text_from_pdf, extract_text_from_image
from app.deps.auth_deps import get_current_user
from app.core.database import db

router = APIRouter(prefix="/ocr-accuracy", tags=["ocr-accuracy"])


def _normalize(s: str) -> str:
    s = (s or "").replace("\r", "\n").lower().strip()
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{2,}", "\n", s)
    return s


def _levenshtein(a: str, b: str) -> int:
    n, m = len(a), len(b)
    if n == 0:
        return m
    if m == 0:
        return n

    dp = list(range(m + 1))
    for i in range(1, n + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, m + 1):
            cur = dp[j]
            cost = 0 if a[i - 1] == b[j - 1] else 1
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + cost)
            prev = cur
    return dp[m]


def _compute_metrics(ground_truth: str, predicted: str):
    gt = _normalize(ground_truth)
    pr = _normalize(predicted)

    cer_dist = _levenshtein(gt, pr)
    cer = cer_dist / max(1, len(gt))
    char_accuracy = max(0.0, 1.0 - cer)

    gt_join = " ".join(gt.split())
    pr_join = " ".join(pr.split())
    wer_dist = _levenshtein(gt_join, pr_join)
    wer = wer_dist / max(1, len(gt_join))
    word_accuracy = max(0.0, 1.0 - wer)

    return {
        "cer": round(cer, 4),
        "wer": round(wer, 4),
        "char_accuracy": round(char_accuracy, 4),
        "word_accuracy": round(word_accuracy, 4),
    }


def _extract_user_id(current_user) -> str:
    """
    Supports multiple payload shapes from auth_deps:
    dict keys: _id, id, user_id, sub
    object attrs: _id, id, user_id, sub
    """
    if isinstance(current_user, dict):
        for k in ("_id", "id", "user_id", "sub"):
            if current_user.get(k):
                return str(current_user[k])
    else:
        for k in ("_id", "id", "user_id", "sub"):
            v = getattr(current_user, k, None)
            if v:
                return str(v)

    raise HTTPException(status_code=401, detail="Unable to resolve user id from token payload")


@router.post("/test")
async def test_ocr_accuracy(
    file: UploadFile = File(...),
    ground_truth_text: str = Form(...),
    current_user=Depends(get_current_user),
):
    try:
        user_id = _extract_user_id(current_user)

        ctype = (file.content_type or "").lower()
        fname = (file.filename or "").lower()

        if "pdf" in ctype or fname.endswith(".pdf"):
            extracted_text = await extract_text_from_pdf(file)
        elif "image" in ctype or fname.endswith((".png", ".jpg", ".jpeg", ".webp")):
            extracted_text = await extract_text_from_image(file)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")

        metrics = _compute_metrics(ground_truth_text, extracted_text)
        now = datetime.now(timezone.utc)

        doc = {
            "user_id": user_id,
            "file_name": file.filename or "unknown",
            "content_type": ctype,
            "ground_truth_text": ground_truth_text,
            "extracted_text": extracted_text,
            "metrics": metrics,
            "created_at": now,
            "updated_at": now,
        }

        res = await db.ocr_accuracy_results.insert_one(doc)

        return {
            "ok": True,
            "id": str(res.inserted_id),
            "file_name": doc["file_name"],
            "metrics": metrics,
            "extracted_text": extracted_text,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR accuracy test failed: {str(e)}")


@router.get("/history")
async def get_ocr_accuracy_history(current_user=Depends(get_current_user)):
    try:
        user_id = _extract_user_id(current_user)

        rows = []
        # ✅ include ground_truth_text and extracted_text for comparison dropdown
        cursor = db.ocr_accuracy_results.find(
            {"user_id": user_id}
        ).sort("created_at", -1)

        async for d in cursor:
            d["id"] = str(d["_id"])
            d.pop("_id", None)
            rows.append(d)

        return {"ok": True, "results": rows}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch OCR history: {str(e)}")