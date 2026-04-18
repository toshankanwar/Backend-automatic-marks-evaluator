import json
import uuid
from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException
from bson import ObjectId
from app.core.database import db
from app.deps.auth_deps import get_current_user
from app.services.ocr_service import extract_text_from_pdf, extract_text_from_image
from app.services.evaluation_service import build_student_result

router = APIRouter(prefix="/users/{user_id}/evaluations/{evaluation_id}", tags=["Upload/Evaluate"])

@router.post("/upload-and-evaluate")
async def upload_and_evaluate(
    user_id: str,
    evaluation_id: str,
    question_schema: str = Form(...),
    answer_key_file: UploadFile = File(...),
    student_files: list[UploadFile] = File(...),
    me=Depends(get_current_user),
):
    if me["sub"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    evaluation = await db.evaluations.find_one({"_id": ObjectId(evaluation_id), "user_id": user_id})
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    parsed_schema = json.loads(question_schema)

    key_text = await extract_text_from_pdf(answer_key_file)

    inserted = 0
    appended = 0
    results_summary = []

    for sf in student_files:
        # image/pdf text extraction
        if sf.filename.lower().endswith(".pdf"):
            student_text = await extract_text_from_pdf(sf)
        else:
            student_text = await extract_text_from_image(sf)

        student_id = sf.filename.rsplit(".", 1)[0].replace(" ", "_") + "_" + str(uuid.uuid4())[:6]

        doc = build_student_result(
            user_id=user_id,
            evaluation_id=evaluation_id,
            student_id=student_id,
            student_name=sf.filename,
            question_schema=parsed_schema,
            key_text=key_text,
            student_text=student_text,
        )

        await db.results.insert_one(doc)
        inserted += 1
        appended += 1
        results_summary.append({
            "student_id": student_id,
            "student_name": sf.filename,
            "total_marks": doc["total_marks"],
            "out_of": doc["total_max_marks"],
        })

    return {
        "message": "Evaluation completed",
        "inserted": inserted,
        "appended": appended,
        "results": results_summary
    }