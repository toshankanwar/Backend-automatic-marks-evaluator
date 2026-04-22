from sentence_transformers import SentenceTransformer, util
from app.utils.text_cleaner import tokenize, clean_text
import hashlib
from typing import Dict, Optional, Any

_model = SentenceTransformer("all-MiniLM-L6-v2")


def _safe_text(x: str) -> str:
    return clean_text(x or "")


def _token_set(x: str) -> set:
    return set(tokenize(_safe_text(x)))


def _ngrams(tokens: list, n: int) -> set:
    if len(tokens) < n:
        return set()
    return set(tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1))


def _emb_key(text: str) -> str:
    # request-scope key; deterministic in one run
    return hashlib.sha256(_safe_text(text).encode("utf-8")).hexdigest()


def keyword_score(model_ans: str, student_ans: str) -> float:
    m_clean = _safe_text(model_ans)
    s_clean = _safe_text(student_ans)

    m_tokens = tokenize(m_clean)
    s_tokens = tokenize(s_clean)

    if not m_tokens:
        return 0.0

    m_uni = set(m_tokens)
    s_uni = set(s_tokens)

    uni_overlap = len(m_uni & s_uni) / max(1, len(m_uni))

    m_bi = _ngrams(m_tokens, 2)
    s_bi = _ngrams(s_tokens, 2)
    if m_bi:
        bi_overlap = len(m_bi & s_bi) / len(m_bi)
        score = 0.7 * uni_overlap + 0.3 * bi_overlap
    else:
        score = uni_overlap

    return max(0.0, min(1.0, score))


def semantic_score(
    model_ans: str,
    student_ans: str,
    embedding_cache: Optional[Dict[str, Any]] = None,
) -> float:
    a = _safe_text(model_ans)
    b = _safe_text(student_ans)
    if not a or not b:
        return 0.0

    embedding_cache = embedding_cache if embedding_cache is not None else {}

    key_a = f"model::{_emb_key(a)}"
    key_b = f"student::{_emb_key(b)}"

    # Cache hits inside single evaluation cycle
    emb_a = embedding_cache.get(key_a)
    if emb_a is None:
        emb_a = _model.encode(a, convert_to_tensor=True, normalize_embeddings=True)
        embedding_cache[key_a] = emb_a

    emb_b = embedding_cache.get(key_b)
    if emb_b is None:
        emb_b = _model.encode(b, convert_to_tensor=True, normalize_embeddings=True)
        embedding_cache[key_b] = emb_b

    sim = util.cos_sim(emb_a, emb_b).item()  # [-1, 1]
    normalized = (sim + 1.0) / 2.0
    return max(0.0, min(1.0, normalized))


def _length_quality_factor(model_ans: str, student_ans: str) -> float:
    m_len = len(tokenize(_safe_text(model_ans)))
    s_len = len(tokenize(_safe_text(student_ans)))

    if m_len == 0:
        return 0.0
    ratio = s_len / m_len

    if ratio >= 0.85:
        return 1.0
    if ratio >= 0.55:
        return 0.92
    if ratio >= 0.35:
        return 0.82
    if ratio >= 0.20:
        return 0.70
    return 0.55


def evaluate_answer(
    model_ans: str,
    student_ans: str,
    max_marks: float,
    embedding_cache: Optional[Dict[str, Any]] = None,  # NEW
) -> dict:
    k = keyword_score(model_ans, student_ans)
    s = semantic_score(model_ans, student_ans, embedding_cache=embedding_cache)

    m_tokens = tokenize(_safe_text(model_ans))
    if len(m_tokens) <= 25:
        wk, ws = 0.45, 0.55
    else:
        wk, ws = 0.30, 0.70

    base = wk * k + ws * s

    lqf = _length_quality_factor(model_ans, student_ans)
    final = max(0.0, min(1.0, base * lqf))

    awarded = round(final * float(max_marks), 2)

    if final >= 0.78:
        fb = "Good answer"
    elif final >= 0.50:
        fb = "Partially correct"
    else:
        fb = "Needs improvement"

    return {
        "keyword_score": round(k, 3),
        "semantic_score": round(s, 3),
        "awarded_marks": awarded,
        "feedback": fb
    }