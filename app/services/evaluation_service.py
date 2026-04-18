from datetime import datetime, timezone
from app.services.parser_service import split_answers_by_question
from app.services.scoring_service import evaluate_answer


def build_student_result(
    user_id: str,
    evaluation_id: str,
    student_id: str,
    student_name: str,
    question_schema: list,
    key_text: str,
    student_text: str,
):
    # pass expected question count to parser for better fallback splitting
    expected_q_count = len(question_schema or [])
    key_map = split_answers_by_question(key_text or "", expected_q_count=expected_q_count)
    stu_map = split_answers_by_question(student_text or "", expected_q_count=expected_q_count)

    q_scores = []
    total = 0.0
    total_max = 0.0

    for q in (question_schema or []):
        q_no = int(q["q_no"])
        max_marks = float(q["max_marks"])
        total_max += max_marks

        km = (key_map.get(q_no, "") or "").strip()
        sm = (stu_map.get(q_no, "") or "").strip()

        # if both missing, give 0 safely
        if not km and not sm:
            ev = {
                "keyword_score": 0.0,
                "semantic_score": 0.0,
                "awarded_marks": 0.0,
                "feedback": "No answer detected",
            }
        else:
            ev = evaluate_answer(km, sm, max_marks)

        row = {
            "q_no": q_no,
            "max_marks": max_marks,
            "awarded_marks": float(ev["awarded_marks"]),
            "keyword_score": float(ev["keyword_score"]),
            "semantic_score": float(ev["semantic_score"]),
            "feedback": ev["feedback"],
        }

        total += row["awarded_marks"]
        q_scores.append(row)

    now = datetime.now(timezone.utc)
    return {
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
    }