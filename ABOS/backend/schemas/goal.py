"""
Schemas for business goal submission and retrieval.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class GoalPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GoalStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"       # workflow being generated
    READY = "ready"             # workflow generated, awaiting execution
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    COMPLIANCE_BLOCKED = "compliance_blocked"


class GoalCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200, description="Short label for the goal")
    description: str = Field(
        min_length=10,
        max_length=2000,
        description="High-level natural-language business goal",
    )
    priority: GoalPriority = GoalPriority.MEDIUM
    target_departments: Optional[List[str]] = Field(
        default=None,
        description="Optional hint — which departments to involve. Leave empty for auto-routing.",
    )
    context: Optional[dict] = Field(
        default=None,
        description="Optional structured context (e.g., customer ID, product line)",
    )
    preferred_language: Optional[str] = Field(
        default=None,
        description=(
            "BCP-47 language tag for the user's preferred language "
            "(e.g. 'hi' for Hindi, 'mr' for Marathi, 'ta' for Tamil, 'en' for English). "
            "If omitted, ABOS auto-detects the language from the goal text. "
            "All outputs will be returned in this language."
        ),
    )


class GoalResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    description: str
    priority: GoalPriority
    status: GoalStatus
    target_departments: Optional[List[str]]
    context: Optional[dict]
    preferred_language: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GoalListResponse(BaseModel):
    goals: List[GoalResponse]
    total: int
