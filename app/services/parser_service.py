import re
from typing import Dict, List, Optional, Tuple

ROMAN_MAP = {
    "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5,
    "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10,
    "xi": 11, "xii": 12, "xiii": 13, "xiv": 14,
    "xv": 15, "xvi": 16, "xvii": 17,
    "xviii": 18, "xix": 19, "xx": 20
}


# =========================================================
# OCR CLEANING
# =========================================================

def _normalize(text: str) -> str:

    if not text:
        return ""

    text = text.replace("\r", "\n")

    text = re.sub(r"[ \t]+", " ", text)

    text = re.sub(r"\n{3,}", "\n\n", text)

    text = re.sub(
        r"\bquestlon\b",
        "question",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\banswेर\b",
        "answer",
        text,
        flags=re.IGNORECASE
    )

    return text.strip()


# =========================================================
# ROMAN
# =========================================================

def _roman_to_int(token: str) -> Optional[int]:

    return ROMAN_MAP.get(
        token.lower().strip()
    )


# =========================================================
# VALIDATION
# =========================================================

def _is_valid_answer(text: str) -> bool:

    if not text:
        return False

    cleaned = re.sub(
        r"[^a-zA-Z0-9]",
        "",
        text
    )

    return len(cleaned) >= 2


# =========================================================
# HEADER PATTERNS
# =========================================================

# STRICT student parser
STUDENT_HEADER_PATTERN = re.compile(
    r"""
    (?im)

    ^\s*

    (?:
        (?:
            q(?:uestion)? |
            ans(?:wer)? |
            a
        )?

        \s*
        [\.\-:)]?
        \s*

        (?:
            (?P<num>\d{1,3}) |
            (?P<roman>[ivxlcdm]{1,8})
        )

        \s*
        [\)\].:\-]?
    )

    \s*$
    """,
    re.VERBOSE
)

# PERMISSIVE teacher parser
TEACHER_HEADER_PATTERN = re.compile(
    r"""
    (?im)

    ^\s*

    (?:
        (?:
            q(?:uestion)? |
            ans(?:wer)? |
            a
        )?

        \s*
        [\.\-:]?
        \s*

        (?:
            (?P<num>\d{1,3}) |
            (?P<roman>[ivxlcdm]{1,8})
        )

        \s*
        [\)\].:\-]?
    )
    """,
    re.VERBOSE
)


# =========================================================
# FIND HEADERS
# =========================================================

def _find_headers(
    text: str,
    expected_set: set,
    teacher_mode: bool = False
) -> List[Tuple[int, int, int, str]]:

    headers = []

    current_pos = 0

    lines = text.split("\n")

    pattern = (
        TEACHER_HEADER_PATTERN
        if teacher_mode
        else STUDENT_HEADER_PATTERN
    )

    for line in lines:

        stripped = line.strip()

        match = pattern.match(stripped)

        if match:

            num = match.group("num")
            roman = match.group("roman")

            q_no = None

            if num:
                q_no = int(num)

            elif roman:
                q_no = _roman_to_int(roman)

            if q_no and (
                not expected_set or
                q_no in expected_set
            ):

                start = current_pos
                end = current_pos + len(line)

                headers.append(
                    (
                        q_no,
                        start,
                        end,
                        line
                    )
                )

        current_pos += len(line) + 1

    return headers


# =========================================================
# CLEAN ANSWER
# =========================================================

def _clean_answer(answer: str) -> str:

    if not answer:
        return ""

    answer = re.sub(
        r"\n{3,}",
        "\n\n",
        answer
    )

    return answer.strip()


# =========================================================
# MAIN PARSER
# =========================================================

def split_answers_by_question(
    text: str,
    expected_qnos: Optional[List[int]] = None,
    teacher_mode: bool = False
) -> Dict[int, str]:

    text = _normalize(text)

    if not text:
        return {}

    expected_set = set(expected_qnos or [])

    headers = _find_headers(
        text,
        expected_set,
        teacher_mode=teacher_mode
    )

    if not headers:
        return {}

    parsed: Dict[int, str] = {}

    pattern = (
        TEACHER_HEADER_PATTERN
        if teacher_mode
        else STUDENT_HEADER_PATTERN
    )

    for i, (
        q_no,
        start,
        end,
        full_line
    ) in enumerate(headers):

        # ============================================
        # SAME LINE ANSWER SUPPORT
        # ============================================

        same_line_answer = ""

        if teacher_mode:

            header_match = pattern.match(
                full_line.strip()
            )

            if header_match:

                same_line_answer = full_line[
                    header_match.end():
                ].strip()

        # ============================================
        # NORMAL ANSWER EXTRACTION
        # ============================================

        answer_start = end

        if i + 1 < len(headers):
            answer_end = headers[i + 1][1]
        else:
            answer_end = len(text)

        answer = text[
            answer_start:answer_end
        ].strip()

        # merge same-line answer
        if same_line_answer:

            if answer:
                answer = (
                    same_line_answer
                    + "\n" +
                    answer
                )
            else:
                answer = same_line_answer

        answer = _clean_answer(answer)

        if not _is_valid_answer(answer):
            continue

        parsed[q_no] = answer

    return dict(sorted(parsed.items()))