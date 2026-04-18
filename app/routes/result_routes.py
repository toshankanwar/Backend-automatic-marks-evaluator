from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from app.core.database import db
from app.deps.auth_deps import get_current_user
from app.schemas.result_schema import UpdateMarksRequest, UpdateQuestionMarksRequest

router = APIRouter(prefix="/users/{user_id}/evaluations/{evaluation_id}", tags=["Results"])

def serialize_result(d: dict):
    return {
        "id": str(d["_id"]),
        "user_id": d["user_id"],
        "evaluation_id": d["evaluation_id"],
        "student_id": d["student_id"],
        "student_name": d["student_name"],
        "total_marks": d["total_marks"],
        "total_max_marks": d["total_max_marks"],
        "question_scores": d.get("question_scores", []),
        "manual_override": d.get("manual_override", False),
        "created_at": d.get("created_at"),
        "updated_at": d.get("updated_at"),
    }

@router.get("/results")
async def list_results(user_id: str, evaluation_id: str, me=Depends(get_current_user)):
    if me["sub"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    cursor = db.results.find({"user_id": user_id, "evaluation_id": evaluation_id}).sort("updated_at", -1)
    docs = await cursor.to_list(length=1000)
    return [serialize_result(d) for d in docs]

@router.get("/results/{student_id}")
async def get_student_result(user_id: str, evaluation_id: str, student_id: str, me=Depends(get_current_user)):
    if me["sub"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    d = await db.results.find_one({"user_id": user_id, "evaluation_id": evaluation_id, "student_id": student_id})
    if not d:
        raise HTTPException(status_code=404, detail="Result not found")
    return serialize_result(d)

@router.patch("/results/{student_id}")
async def update_student_marks(
    user_id: str,
    evaluation_id: str,
    student_id: str,
    payload: UpdateMarksRequest,
    me=Depends(get_current_user),
):
    if me["sub"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    d = await db.results.find_one({"user_id": user_id, "evaluation_id": evaluation_id, "student_id": student_id})
    if not d:
        raise HTTPException(status_code=404, detail="Result not found")

    await db.results.update_one(
        {"_id": d["_id"]},
        {"$set": {
            "total_marks": payload.total_marks,
            "manual_override": True,
            "override_note": payload.note,
            "updated_at": datetime.now(timezone.utc)
        }}
    )
    return {"message": "Marks updated"}

# ✅ NEW: per-question marks update
@router.patch("/results/{student_id}/questions/{q_no}")
async def update_student_question_marks(
    user_id: str,
    evaluation_id: str,
    student_id: str,
    q_no: int,
    payload: UpdateQuestionMarksRequest,
    me=Depends(get_current_user),
):
    if me["sub"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    d = await db.results.find_one({"user_id": user_id, "evaluation_id": evaluation_id, "student_id": student_id})
    if not d:
        raise HTTPException(status_code=404, detail="Result not found")

    question_scores = d.get("question_scores", [])
    if not question_scores:
        raise HTTPException(status_code=400, detail="No question-wise data available")

    found = False
    for q in question_scores:
        if int(q.get("q_no", -1)) == int(q_no):
            max_marks = float(q.get("max_marks", 0))
            if payload.awarded_marks > max_marks:
                raise HTTPException(status_code=400, detail=f"Marks cannot exceed max_marks ({max_marks})")
            q["awarded_marks"] = payload.awarded_marks
            q["feedback"] = f"{q.get('feedback', '')} | Teacher override".strip(" |")
            found = True
            break

    if not found:
        raise HTTPException(status_code=404, detail=f"Question {q_no} not found")

    # recompute total from updated question scores
    new_total = sum(float(q.get("awarded_marks", 0)) for q in question_scores)

    await db.results.update_one(
        {"_id": d["_id"]},
        {"$set": {
            "question_scores": question_scores,
            "total_marks": new_total,
            "manual_override": True,
            "override_note": payload.note,
            "updated_at": datetime.now(timezone.utc),
        }}
    )

    return {"message": f"Q{q_no} marks updated", "total_marks": new_total}