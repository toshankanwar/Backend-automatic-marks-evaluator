from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class QuestionScore(BaseModel):
    q_no: int
    max_marks: float
    awarded_marks: float
    keyword_score: float
    semantic_score: float
    feedback: str

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
    created_at: datetime
    updated_at: datetime

class UpdateMarksRequest(BaseModel):
    total_marks: float
    note: Optional[str] = ""

class UpdateQuestionMarksRequest(BaseModel):
    awarded_marks: float = Field(..., ge=0)
    note: str = "Teacher updated question marks"