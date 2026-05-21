from sentence_transformers import SentenceTransformer, util
from app.utils.text_cleaner import tokenize, clean_text

import hashlib
import re

from typing import Dict, Optional, Any


# =========================================================
# MODEL
# =========================================================

_model = SentenceTransformer("all-MiniLM-L6-v2")


# =========================================================
# BASIC HELPERS
# =========================================================

def _safe_text(x: str) -> str:

    return clean_text(x or "")


def _token_set(x: str) -> set:

    return set(tokenize(_safe_text(x)))


def _emb_key(text: str) -> str:

    return hashlib.sha256(
        _safe_text(text).encode("utf-8")
    ).hexdigest()


# =========================================================
# SEMANTIC SCORE
# =========================================================

def semantic_score(
    model_ans: str,
    student_ans: str,
    embedding_cache: Optional[Dict[str, Any]] = None,
) -> float:

    a = _safe_text(model_ans)
    b = _safe_text(student_ans)

    if not a or not b:
        return 0.0

    embedding_cache = (
        embedding_cache
        if embedding_cache is not None
        else {}
    )

    key_a = f"model::{_emb_key(a)}"
    key_b = f"student::{_emb_key(b)}"

    emb_a = embedding_cache.get(key_a)

    if emb_a is None:

        emb_a = _model.encode(
            a,
            convert_to_tensor=True,
            normalize_embeddings=True
        )

        embedding_cache[key_a] = emb_a

    emb_b = embedding_cache.get(key_b)

    if emb_b is None:

        emb_b = _model.encode(
            b,
            convert_to_tensor=True,
            normalize_embeddings=True
        )

        embedding_cache[key_b] = emb_b

    sim = util.cos_sim(emb_a, emb_b).item()

    normalized = (sim + 1.0) / 2.0

    return max(0.0, min(1.0, normalized))


# =========================================================
# KEYWORD SCORE
# =========================================================

def keyword_score(
    model_ans: str,
    student_ans: str
) -> float:

    model_tokens = _token_set(model_ans)
    student_tokens = _token_set(student_ans)

    if not model_tokens:
        return 0.0

    overlap = model_tokens & student_tokens

    score = (
        len(overlap)
        / len(model_tokens)
    )

    return max(0.0, min(1.0, score))


# =========================================================
# TOKEN LENGTH FACTOR
# =========================================================

def token_length_factor(
    model_ans: str,
    student_ans: str
) -> float:

    model_tokens = tokenize(
        _safe_text(model_ans)
    )

    student_tokens = tokenize(
        _safe_text(student_ans)
    )

    m_len = len(model_tokens)
    s_len = len(student_tokens)

    if m_len == 0:
        return 1.0

    ratio = s_len / m_len

    # -------------------------------------
    # TOKEN RATIO BASED SCORING
    # -------------------------------------

    if ratio >= 1.0:
        return 1.0

    if ratio >= 0.8:
        return 0.95

    if ratio >= 0.6:
        return 0.85

    if ratio >= 0.4:
        return 0.70

    if ratio >= 0.25:
        return 0.55

    return 0.35


# =========================================================
# MAIN EVALUATION
# =========================================================

def evaluate_answer(
    model_ans: str,
    student_ans: str,
    max_marks: float,
    embedding_cache: Optional[Dict[str, Any]] = None,
) -> dict:

    model_ans = _safe_text(model_ans)
    student_ans = _safe_text(student_ans)

    # =====================================================
    # EMPTY ANSWER
    # =====================================================

    if not student_ans.strip():

        return {
            "keyword_score": 0.0,
            "semantic_score": 0.0,
            "token_factor": 0.0,
            "final_score": 0.0,
            "awarded_marks": 0.0,
            "feedback": "No answer provided"
        }

    # =====================================================
    # SEMANTIC SCORE (70%)
    # =====================================================

    semantic = semantic_score(
        model_ans,
        student_ans,
        embedding_cache=embedding_cache
    )

    # =====================================================
    # KEYWORD SCORE (30%)
    # =====================================================

    keyword = keyword_score(
        model_ans,
        student_ans
    )

    # =====================================================
    # BASE SCORE
    # =====================================================

    base_score = (
        (semantic * 0.70) +
        (keyword * 0.30)
    )

    # =====================================================
    # TOKEN FACTOR
    # =====================================================

    token_factor = token_length_factor(
        model_ans,
        student_ans
    )

    # =====================================================
    # FINAL SCORE
    # =====================================================

    final_score = (
        base_score *
        token_factor
    )

    final_score = max(
        0.0,
        min(1.0, final_score)
    )

    awarded_marks = round(
        final_score * float(max_marks),
        2
    )

    # =====================================================
    # FEEDBACK
    # =====================================================

    if final_score >= 0.80:
        feedback = "Excellent answer"

    elif final_score >= 0.65:
        feedback = "Good answer"

    elif final_score >= 0.45:
        feedback = "Partially correct"

    elif final_score >= 0.25:
        feedback = "Needs improvement"

    else:
        feedback = "Incorrect answer"

    return {

        "keyword_score": round(keyword, 3),

        "semantic_score": round(semantic, 3),

        "token_factor": round(token_factor, 3),

        "final_score": round(final_score, 3),

        "awarded_marks": awarded_marks,

        "feedback": feedback
    }