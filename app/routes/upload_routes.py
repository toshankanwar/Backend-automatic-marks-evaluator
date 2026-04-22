# app/routes/upload_evaluate_routes.py
import json
import uuid
import time
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, Form, UploadFile, File, HTTPException

from app.core.database import db
from app.deps.auth_deps import get_current_user
from app.services.ocr_service import extract_text_from_pdf, extract_text_from_image
from app.services.evaluation_service import build_student_result
from app.utils.process_tracker import ProcessTracker

router = APIRouter(prefix="/users/{user_id}/evaluations/{evaluation_id}", tags=["Upload/Evaluate"])


def _ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


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

    try:
        eval_obj_id = ObjectId(evaluation_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid evaluation_id")

    evaluation = await db.evaluations.find_one({"_id": eval_obj_id, "user_id": user_id})
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    try:
        parsed_schema = json.loads(question_schema)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid question_schema JSON")

    batch_start = time.perf_counter()
    batch_totals = {
        "upload_ms": 0,
        "ocr_ms": 0,
        "parser_ms": 0,
        "scoring_ms": 0,
    }

    # answer key timing
    key_tracker = ProcessTracker(submission_id=f"{evaluation_id}_ANSWER_KEY", student_id="ANSWER_KEY")
    key_tracker.stage_start("upload")
    key_tracker.stage_end("upload", {"filename": answer_key_file.filename})
    key_tracker.stage_start("ocr")
    try:
        key_text = await extract_text_from_pdf(answer_key_file)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Answer key OCR failed: {str(e)}")
    key_tracker.stage_end("ocr", {"chars_extracted": len(key_text or "")})
    key_timing = key_tracker.finalize()

    inserted = 0
    appended = 0
    results_summary = []

    for sf in student_files:
        student_id = sf.filename.rsplit(".", 1)[0].replace(" ", "_") + "_" + str(uuid.uuid4())[:6]
        tracker = ProcessTracker(submission_id=f"{evaluation_id}:{student_id}", student_id=student_id)

        # upload stage (logical)
        t_upload = time.perf_counter()
        tracker.stage_start("upload")
        tracker.stage_end("upload", {"filename": sf.filename, "content_type": sf.content_type})
        upload_ms = _ms(t_upload)
        batch_totals["upload_ms"] += upload_ms

        # OCR stage
        t_ocr = time.perf_counter()
        tracker.stage_start("ocr")
        try:
            if sf.filename.lower().endswith(".pdf"):
                student_text = await extract_text_from_pdf(sf)
            else:
                student_text = await extract_text_from_image(sf)
        except Exception as e:
            tracker.log("PROCESS_FAILED", {"stage": "ocr", "error": str(e)})
            failed_timing = tracker.finalize()
            results_summary.append({
                "student_id": student_id,
                "student_name": sf.filename,
                "status": "FAILED_AT_OCR",
                "error": str(e),
                "timing": failed_timing,
                "timeline": tracker.events
            })
            print(f"[TIMING][{student_id}] FAILED_AT_OCR upload={upload_ms}ms")
            continue

        tracker.stage_end("ocr", {"chars_extracted": len(student_text or "")})
        ocr_ms = _ms(t_ocr)
        batch_totals["ocr_ms"] += ocr_ms

        # parser + scoring inside build_student_result
        try:
            doc = build_student_result(
                user_id=user_id,
                evaluation_id=evaluation_id,
                student_id=student_id,
                student_name=sf.filename,
                question_schema=parsed_schema,
                key_text=key_text,
                student_text=student_text,
                tracker=tracker,
            )
        except Exception as e:
            tracker.log("PROCESS_FAILED", {"stage": "evaluation", "error": str(e)})
            failed_timing = tracker.finalize()
            results_summary.append({
                "student_id": student_id,
                "student_name": sf.filename,
                "status": "FAILED_AT_EVALUATION",
                "error": str(e),
                "timing": failed_timing,
                "timeline": tracker.events
            })
            print(f"[TIMING][{student_id}] FAILED_AT_EVAL upload={upload_ms}ms ocr={ocr_ms}ms")
            continue

        # aggregate parser/scoring from student timing
        st_timing = doc.get("timing", {}) or {}
        parser_ms = int(st_timing.get("parser_ms") or 0)
        scoring_ms = int(st_timing.get("scoring_ms") or 0)
        batch_totals["parser_ms"] += parser_ms
        batch_totals["scoring_ms"] += scoring_ms

        await db.results.insert_one(doc)
        inserted += 1
        appended += 1

        print(
            f"[TIMING][{student_id}] upload={upload_ms}ms ocr={ocr_ms}ms "
            f"parser={parser_ms}ms scoring={scoring_ms}ms total={st_timing.get('total_ms', 0)}ms"
        )

        results_summary.append({
            "student_id": student_id,
            "student_name": sf.filename,
            "total_marks": doc["total_marks"],
            "out_of": doc["total_max_marks"],
            "validation": doc.get("validation", {}),
            "timing": doc.get("timing", {}),
            "timeline": doc.get("timeline", []),
        })

    batch_total_ms = _ms(batch_start)
    batch_timing = {
        "students_count": len(student_files),
        "batch_upload_ms": batch_totals["upload_ms"],
        "batch_ocr_ms": batch_totals["ocr_ms"],
        "batch_parser_ms": batch_totals["parser_ms"],
        "batch_scoring_ms": batch_totals["scoring_ms"],
        "batch_total_ms": batch_total_ms,
        "avg_total_ms_per_student": int(batch_total_ms / len(student_files)) if student_files else 0,
    }

    # persist batch summary on evaluation doc (latest run)
    await db.evaluations.update_one(
        {"_id": eval_obj_id},
        {"$set": {
            "last_batch_timing": batch_timing,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }}
    )

    print("\n========== EVALUATION BATCH TIMING ==========")
    print(f"Students       : {batch_timing['students_count']}")
    print(f"Upload Total   : {batch_timing['batch_upload_ms']} ms")
    print(f"OCR Total      : {batch_timing['batch_ocr_ms']} ms")
    print(f"Parser Total   : {batch_timing['batch_parser_ms']} ms")
    print(f"Scoring Total  : {batch_timing['batch_scoring_ms']} ms")
    print(f"Batch Total    : {batch_timing['batch_total_ms']} ms")
    print("=============================================\n")

    return {
        "message": "Evaluation completed",
        "inserted": inserted,
        "appended": appended,
        "answer_key_timing": key_timing,
        "batch_timing": batch_timing,   # NEW
        "results": results_summary
    }