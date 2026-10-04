"""
Schemas for the Level-2 explicit-feedback memory layer.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class FeedbackRating(str, Enum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    PARTIAL = "partial"


class FeedbackCreateRequest(BaseModel):
    execution_id: UUID = Field(description="The execution this feedback refers to")
    rating: FeedbackRating
    correction: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Free-text correction if rating is incorrect or partial",
    )
    suggested_agent: Optional[str] = Field(
        default=None,
        description="If routing was wrong, which agent should have handled this?",
    )


class FeedbackResponse(BaseModel):
    id: UUID
    user_id: UUID
    execution_id: UUID
    rating: FeedbackRating
    correction: Optional[str]
    suggested_agent: Optional[str]
    embedding: Optional[List[float]] = None   # pgvector embedding, omitted in most responses
    created_at: datetime

    model_config = {"from_attributes": True}


class FeedbackListResponse(BaseModel):
    feedback: List[FeedbackResponse]
    total: int
