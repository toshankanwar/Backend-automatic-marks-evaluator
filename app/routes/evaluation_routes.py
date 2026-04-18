from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timezone
from bson import ObjectId
from app.core.database import db
from app.deps.auth_deps import get_current_user
from app.schemas.evaluation_schema import CreateEvaluationRequest

router = APIRouter(prefix="/users/{user_id}/evaluations", tags=["Evaluations"])

def serialize_eval(doc: dict):
    return {
        "id": str(doc["_id"]),
        "user_id": doc["user_id"],
        "title": doc["title"],
        "subject": doc["subject"],
        "question_schema": doc["question_schema"],
        "created_at": doc["created_at"],
        "updated_at": doc["updated_at"],
    }

@router.post("")
async def create_evaluation(user_id: str, payload: CreateEvaluationRequest, me=Depends(get_current_user)):
    if me["sub"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    now = datetime.now(timezone.utc)
    doc = {
        "user_id": user_id,
        "title": payload.title.strip(),
        "subject": payload.subject.strip(),
        "question_schema": [q.model_dump() for q in payload.question_schema],
        "created_at": now,
        "updated_at": now,
    }
    result = await db.evaluations.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_eval(doc)

@router.get("")
async def list_evaluations(user_id: str, me=Depends(get_current_user)):
    if me["sub"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    cursor = db.evaluations.find({"user_id": user_id}).sort("updated_at", -1)
    docs = await cursor.to_list(length=200)
    return [serialize_eval(d) for d in docs]

@router.get("/{evaluation_id}")
async def get_evaluation(user_id: str, evaluation_id: str, me=Depends(get_current_user)):
    if me["sub"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    doc = await db.evaluations.find_one({"_id": ObjectId(evaluation_id), "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return serialize_eval(doc)

@router.delete("/{evaluation_id}", status_code=status.HTTP_200_OK)
async def delete_evaluation(user_id: str, evaluation_id: str):
    if not ObjectId.is_valid(evaluation_id):
        raise HTTPException(status_code=400, detail="Invalid evaluation_id")

    eval_obj = ObjectId(evaluation_id)

    # try both ObjectId and string match for user_id
    query = {
        "_id": eval_obj,
        "$or": [
            {"user_id": ObjectId(user_id)} if ObjectId.is_valid(user_id) else {"user_id": user_id},
            {"user_id": user_id},
        ],
    }

    evaluation = await db.evaluations.find_one(query)
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    # delete related results (same user id mismatch-safe condition)
    await db.results.delete_many({
        "evaluation_id": eval_obj,
        "$or": [
            {"user_id": ObjectId(user_id)} if ObjectId.is_valid(user_id) else {"user_id": user_id},
            {"user_id": user_id},
        ],
    })

    await db.evaluations.delete_one({"_id": eval_obj})
    return {"message": "Evaluation deleted successfully"}