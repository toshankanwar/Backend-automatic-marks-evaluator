# app/schemas/result_schema.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class QuestionScore(BaseModel):
    q_no: int
    max_marks: float
    awarded_marks: float
    keyword_score: float
    semantic_score: float
    feedback: str
    status: Optional[str] = None


class ValidationOut(BaseModel):
    expected_questions: int = 0
    attempted_questions: int = 0
    missing_questions: List[int] = []
    status: str = "N/A"
    completion_ratio: float = 0.0


class TimingOut(BaseModel):
    total_ms: Optional[int] = None
    upload_ms: Optional[int] = None
    ocr_ms: Optional[int] = None
    parser_ms: Optional[int] = None
    scoring_ms: Optional[int] = None


class BatchTimingOut(BaseModel):
    students_count: int = 0
    batch_upload_ms: int = 0
    batch_ocr_ms: int = 0
    batch_parser_ms: int = 0
    batch_scoring_ms: int = 0
    batch_total_ms: int = 0
    avg_total_ms_per_student: int = 0


class TimelineEvent(BaseModel):
    event: str
    timestamp: str
    submission_id: Optional[str] = None
    student_id: Optional[str] = None
    meta: Dict[str, Any] = {}


class StudentResultOut(BaseModel):
    id: str
    user_id: str
    evaluation_id: str
    student_id: str
    student_name: str
    total_marks: float
    total_max_marks: float
    question_scores: List[QuestionScore]
    manual_override: bool = False
    validation: Optional[ValidationOut] = None
    timing: Optional[TimingOut] = None
    timeline: Optional[List[TimelineEvent]] = None
    created_at: datetime
    updated_at: datetime


class ResultsListOut(BaseModel):
    batch_timing: Optional[BatchTimingOut] = None
    results: List[StudentResultOut] = []


class UpdateMarksRequest(BaseModel):
    total_marks: float
    note: Optional[str] = ""


class UpdateQuestionMarksRequest(BaseModel):
    awarded_marks: float = Field(..., ge=0)
    note: str = "Teacher updated question marks"