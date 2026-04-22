from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from app.services.parser_service import split_answers_by_question
from app.services.scoring_service import evaluate_answer
from app.utils.process_tracker import ProcessTracker


def build_student_result(
    user_id: str,
    evaluation_id: str,
    student_id: str,
    student_name: str,
    question_schema: list,
    key_text: str,
    student_text: str,
    tracker: Optional[ProcessTracker] = None,
    embedding_cache: Optional[Dict[str, Any]] = None,  # NEW
):
    tracker = tracker or ProcessTracker(submission_id=evaluation_id, student_id=str(student_id))
    tracker.log("UPLOAD_COMPLETED")

    expected_q_count = len(question_schema or [])

    tracker.stage_start("parser")
    key_map = split_answers_by_question(key_text or "", expected_q_count=expected_q_count)
    stu_map = split_answers_by_question(student_text or "", expected_q_count=expected_q_count)
    tracker.stage_end("parser", {
        "expected_questions": expected_q_count,
        "parsed_key_questions": len(key_map),
        "parsed_student_questions": len(stu_map),
    })

    expected_qnos = [int(q["q_no"]) for q in (question_schema or [])]
    attempted_qnos = sorted([q_no for q_no in expected_qnos if (stu_map.get(q_no, "") or "").strip()])
    missing_qnos = [q_no for q_no in expected_qnos if q_no not in attempted_qnos]

    validation_status = "COMPLETE_ATTEMPT" if len(missing_qnos) == 0 else "PARTIAL_ATTEMPT"
    if validation_status == "PARTIAL_ATTEMPT":
        tracker.log("VALIDATION_WARNING", {
            "message": "Some questions were not attempted or not detected.",
            "missing_questions": missing_qnos
        })

    tracker.stage_start("scoring")
    q_scores: List[Dict[str, Any]] = []
    total = 0.0
    total_max = 0.0

    for q in (question_schema or []):
        q_no = int(q["q_no"])
        max_marks = float(q["max_marks"])
        total_max += max_marks

        km = (key_map.get(q_no, "") or "").strip()
        sm = (stu_map.get(q_no, "") or "").strip()

        if not sm:
            ev = {
                "keyword_score": 0.0,
                "semantic_score": 0.0,
                "awarded_marks": 0.0,
                "feedback": "Not Attempted",
                "status": "MISSING_STUDENT_ANSWER"
            }
        elif not km:
            ev = {
                "keyword_score": 0.0,
                "semantic_score": 0.0,
                "awarded_marks": 0.0,
                "feedback": "Answer key missing for this question",
                "status": "MISSING_KEY_ANSWER"
            }
        else:
            base = evaluate_answer(
                km,
                sm,
                max_marks,
                embedding_cache=embedding_cache,  # NEW
            )
            ev = {**base, "status": "EVALUATED"}

        row = {
            "q_no": q_no,
            "max_marks": max_marks,
            "awarded_marks": float(ev["awarded_marks"]),
            "keyword_score": float(ev["keyword_score"]),
            "semantic_score": float(ev["semantic_score"]),
            "feedback": ev["feedback"],
            "status": ev["status"],
        }

        total += row["awarded_marks"]
        q_scores.append(row)

    tracker.stage_end("scoring", {"evaluated_questions": len(q_scores)})

    now = datetime.now(timezone.utc)
    timing = tracker.finalize()

    result = {
        "user_id": user_id,
        "evaluation_id": evaluation_id,
        "student_id": str(student_id),
        "student_name": (student_name or "").strip() or str(student_id),
        "question_scores": q_scores,
        "total_marks": round(total, 2),
        "total_max_marks": round(total_max, 2),
        "manual_override": False,
        "created_at": now,
        "updated_at": now,
        "validation": {
            "expected_questions": expected_q_count,
            "attempted_questions": len(attempted_qnos),
            "missing_questions": missing_qnos,
            "status": validation_status,
            "completion_ratio": round((len(attempted_qnos) / expected_q_count), 3) if expected_q_count else 0.0
        },
        "timing": timing,
        "timeline": tracker.events,
    }

    return result