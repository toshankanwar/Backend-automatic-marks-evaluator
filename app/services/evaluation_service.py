import re
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

from app.services.parser_service import split_answers_by_question
from app.services.scoring_service import evaluate_answer
from app.utils.process_tracker import ProcessTracker


# =========================================================
# TEXT NORMALIZATION
# =========================================================

def _normalize_text(text: str) -> str:

    text = (text or "").strip().lower()

    text = re.sub(r"\s+", " ", text)

    return text


# =========================================================
# VERY LIGHT VALIDATION
# IMPORTANT:
# Only reject truly empty/garbage answers
# Do NOT reject short academic answers
# =========================================================

def _is_valid_answer(text: str) -> bool:

    if not text:
        return False

    text = text.strip()

    # empty
    if not text:
        return False

    # remove symbols
    cleaned = re.sub(
        r"[^a-zA-Z0-9]",
        "",
        text
    )

    # reject only pure garbage
    if len(cleaned) < 2:
        return False

    return True


# =========================================================
# DUPLICATE DETECTION
# IMPORTANT FIX:
# ONLY exact duplicates
# No substring matching
# =========================================================

def _is_duplicate_answer(
    current_answer: str,
    previous_answers: List[str]
) -> bool:

    current = _normalize_text(current_answer)

    if not current:
        return False

    for prev in previous_answers:

        prev = _normalize_text(prev)

        # ONLY exact duplicate
        if current == prev:
            return True

    return False


# =========================================================
# MAIN RESULT BUILDER
# =========================================================

def build_student_result(
    user_id: str,
    evaluation_id: str,
    student_id: str,
    student_name: str,
    question_schema: list,
    key_text: str,
    student_text: str,
    tracker: Optional[ProcessTracker] = None,
    embedding_cache: Optional[Dict[str, Any]] = None,
):

    tracker = tracker or ProcessTracker(
        submission_id=evaluation_id,
        student_id=str(student_id)
    )

    tracker.log("UPLOAD_COMPLETED")

    # =====================================================
    # EXPECTED QUESTIONS
    # =====================================================

    expected_qnos = []

    for q in (question_schema or []):

        try:

            q_no = int(q["q_no"])

            if q_no not in expected_qnos:
                expected_qnos.append(q_no)

        except Exception:
            continue

    expected_qnos = sorted(expected_qnos)

    expected_q_count = len(expected_qnos)

    # =====================================================
    # PARSER
    # =====================================================

    tracker.stage_start("parser")

    key_map = split_answers_by_question(
        key_text or "",
        expected_qnos=expected_qnos
    )

    stu_map = split_answers_by_question(
        student_text or "",
        expected_qnos=expected_qnos
    )

    tracker.stage_end(
        "parser",
        {
            "expected_questions": expected_q_count,
            "parsed_key_questions": len(key_map),
            "parsed_student_questions": len(stu_map),
            "parsed_student_qnos": list(stu_map.keys()),
        }
    )

    # =====================================================
    # VALIDATE STUDENT ANSWERS
    # IMPORTANT FIX:
    # Do NOT over-filter answers
    # =====================================================

    parsed_student_qnos = set()

    validated_student_answers = {}

    used_answers = []

    for q_no in expected_qnos:

        ans = (
            stu_map.get(q_no, "") or ""
        ).strip()

        # only reject truly empty
        if not _is_valid_answer(ans):
            continue

        # duplicate check
        if _is_duplicate_answer(
            ans,
            used_answers
        ):

            tracker.log(
                "DUPLICATE_ANSWER_DETECTED",
                {
                    "question": q_no
                }
            )

            continue

        parsed_student_qnos.add(q_no)

        validated_student_answers[q_no] = ans

        used_answers.append(ans)

    # =====================================================
    # ATTEMPT ANALYSIS
    # =====================================================

    attempted_qnos = [
        q_no
        for q_no in expected_qnos
        if q_no in parsed_student_qnos
    ]

    missing_qnos = [
        q_no
        for q_no in expected_qnos
        if q_no not in parsed_student_qnos
    ]

    completion_ratio = (
        round(
            len(attempted_qnos)
            / expected_q_count,
            3
        )
        if expected_q_count
        else 0.0
    )

    parser_confidence = completion_ratio

    # =====================================================
    # VALIDATION STATUS
    # =====================================================

    if parser_confidence <= 0.30:

        validation_status = (
            "LOW_PARSER_CONFIDENCE"
        )

    elif missing_qnos:

        validation_status = (
            "PARTIAL_ATTEMPT"
        )

    else:

        validation_status = (
            "COMPLETE_ATTEMPT"
        )

    # =====================================================
    # SCORING
    # =====================================================

    tracker.stage_start("scoring")

    q_scores: List[Dict[str, Any]] = []

    total = 0.0

    total_max = 0.0

    for q in (question_schema or []):

        q_no = int(q["q_no"])

        max_marks = float(q["max_marks"])

        total_max += max_marks

        # key answer
        km = (
            key_map.get(q_no, "") or ""
        ).strip()

        # student answer
        sm = (
            validated_student_answers.get(
                q_no,
                ""
            ) or ""
        ).strip()

        # =================================================
        # STUDENT ANSWER MISSING
        # =================================================

        if q_no not in parsed_student_qnos:

            ev = {
                "keyword_score": 0.0,
                "semantic_score": 0.0,
                "awarded_marks": 0.0,
                "feedback": "Not Attempted",
                "status": "MISSING_STUDENT_ANSWER"
            }

        # =================================================
        # KEY ANSWER MISSING
        # IMPORTANT FIX:
        # only check empty key
        # =================================================

        elif not km.strip():

            ev = {
                "keyword_score": 0.0,
                "semantic_score": 0.0,
                "awarded_marks": 0.0,
                "feedback": "Answer key missing",
                "status": "MISSING_KEY_ANSWER"
            }

        # =================================================
        # NORMAL EVALUATION
        # =================================================

        else:

            try:

                base = evaluate_answer(
                    km,
                    sm,
                    max_marks,
                    embedding_cache=embedding_cache,
                )

                ev = {
                    **base,
                    "status": "EVALUATED"
                }

            except Exception as e:

                tracker.log(
                    "SCORING_ERROR",
                    {
                        "question": q_no,
                        "error": str(e)
                    }
                )

                ev = {
                    "keyword_score": 0.0,
                    "semantic_score": 0.0,
                    "awarded_marks": 0.0,
                    "feedback": "Evaluation failed",
                    "status": "SCORING_ERROR"
                }

        # =================================================
        # FINAL ROW
        # =================================================

        row = {

            "q_no": q_no,

            "max_marks": max_marks,

            "awarded_marks": round(
                float(ev["awarded_marks"]),
                2
            ),

            "keyword_score": round(
                float(ev["keyword_score"]),
                3
            ),

            "semantic_score": round(
                float(ev["semantic_score"]),
                3
            ),

            "feedback": ev["feedback"],

            "status": ev["status"],
        }

        total += row["awarded_marks"]

        q_scores.append(row)

    tracker.stage_end(
        "scoring",
        {
            "evaluated_questions": len(q_scores)
        }
    )

    # =====================================================
    # FINAL RESULT
    # =====================================================

    now = datetime.now(timezone.utc)

    timing = tracker.finalize()

    result = {

        "user_id": user_id,

        "evaluation_id": evaluation_id,

        "student_id": str(student_id),

        "student_name": (
            (student_name or "").strip()
            or str(student_id)
        ),

        "question_scores": q_scores,

        "total_marks": round(total, 2),

        "total_max_marks": round(total_max, 2),

        "manual_override": False,

        "created_at": now,

        "updated_at": now,

        "validation": {

            "expected_questions":
                expected_q_count,

            "attempted_questions":
                len(attempted_qnos),

            "attempted_qnos":
                attempted_qnos,

            "missing_questions":
                missing_qnos,

            "parsed_student_qnos":
                sorted(
                    list(parsed_student_qnos)
                ),

            "status":
                validation_status,

            "completion_ratio":
                completion_ratio,

            "parser_confidence":
                parser_confidence,
        },

        "timing": timing,

        "timeline": tracker.events,
    }

    return result