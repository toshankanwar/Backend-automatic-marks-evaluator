from pydantic import BaseModel, Field
from typing import List
from datetime import datetime

class QuestionItem(BaseModel):
    q_no: int
    max_marks: float

class CreateEvaluationRequest(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    subject: str = Field(min_length=2, max_length=100)
    question_schema: List[QuestionItem]

class EvaluationOut(BaseModel):
    id: str
    user_id: str
    title: str
    subject: str
    question_schema: List[QuestionItem]
    created_at: datetime
    updated_at: datetime