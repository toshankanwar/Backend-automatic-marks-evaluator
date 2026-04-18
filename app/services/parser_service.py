import re
from typing import Dict, List, Tuple

ROMAN_MAP = {
    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5,
    "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10,
    "xi": 11, "xii": 12, "xiii": 13, "xiv": 14, "xv": 15,
    "xvi": 16, "xvii": 17, "xviii": 18, "xix": 19, "xx": 20
}

def _normalize_ocr_noise(text: str) -> str:
    if not text:
        return ""
    t = text.replace("\r", "\n")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)

    # Common OCR misreads
    t = re.sub(r"\bquestlon\b", "question", t, flags=re.IGNORECASE)
    t = re.sub(r"\banswेर\b", "answer", t, flags=re.IGNORECASE)
    t = re.sub(r"\bq[\|lI]\b", "q1", t, flags=re.IGNORECASE)  # ql/qI -> q1

    return t.strip()

def _roman_to_int(token: str) -> int | None:
    return ROMAN_MAP.get(token.strip().lower())

def _to_qno(num_token: str | None, roman_token: str | None) -> int | None:
    if num_token and num_token.isdigit():
        return int(num_token)
    if roman_token:
        return _roman_to_int(roman_token)
    return None

def _merge_duplicate_blocks(blocks: List[Tuple[int, str]]) -> Dict[int, str]:
    out: Dict[int, str] = {}
    for q_no, txt in blocks:
        txt = txt.strip()
        if not txt:
            continue
        if q_no in out:
            out[q_no] = (out[q_no] + "\n" + txt).strip()
        else:
            out[q_no] = txt
    return out

def _fallback_split(text: str, expected_q_count: int = 0) -> Dict[int, str]:
    chunks = [c.strip() for c in re.split(r"\n\s*\n+", text) if c.strip()]
    if not chunks:
        return {1: text.strip()} if text.strip() else {}
    if expected_q_count > 0 and len(chunks) >= expected_q_count:
        chunks = chunks[:expected_q_count]
    return {i + 1: c for i, c in enumerate(chunks)}

def split_answers_by_question(text: str, expected_q_count: int = 0) -> Dict[int, str]:
    """
    Supports:
    - Q1, Q.1, Question 1
    - Ans 1, Ans.1, Answer 1, Answer:1, A1, A.1
    - 1), 1., 1:, (1)
    - plain line: "1" (just number on a line)
    - roman numerals for prefixed forms
    """
    raw = _normalize_ocr_noise(text)
    if not raw:
        return {}

    pattern = re.compile(
        r"""
        (?:(?<=^)|(?<=\n))\s*
        (?:
            # Q / Question / Ans / Answer / A prefix
            (?:
                q(?:uestion)?|
                ans(?:wer)?|
                a
            )\s*[\.\-:)]?\s*
            (?:
                (?P<num1>\d{1,3})|
                (?P<rom1>[ivxlcdm]{1,8})
            )\b

            |

            # Numbered header like 1)  1.  1:  (1)
            [\(\[]?\s*
            (?:
                (?P<num2>\d{1,3})|
                (?P<rom2>[ivxlcdm]{1,8})
            )\s*[\)\].:\-]

            |

            # Plain line number header: "1" (only number on line)
            (?P<num3>\d{1,3})\s*(?=\n|$)
        )
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    matches = list(pattern.finditer(raw))
    if not matches:
        return _fallback_split(raw, expected_q_count)

    blocks: List[Tuple[int, str]] = []
    for i, m in enumerate(matches):
        q_no = _to_qno(
            m.group("num1") or m.group("num2") or m.group("num3"),
            m.group("rom1") or m.group("rom2"),
        )
        if q_no is None:
            continue

        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        ans = raw[start:end].strip()

        if len(ans) < 1:
            continue

        blocks.append((q_no, ans))

    if not blocks:
        return _fallback_split(raw, expected_q_count)

    out = _merge_duplicate_blocks(blocks)

    if expected_q_count > 0:
        out = {k: out[k] for k in sorted(out) if 1 <= k <= expected_q_count}

        # If too weak parse, fallback sometimes better
        if len(out) <= 1 and expected_q_count > 1:
            fb = _fallback_split(raw, expected_q_count)
            if len(fb) > len(out):
                return fb

    return out