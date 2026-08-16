"""
Schemas for generated workflows and their steps.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class WorkflowStatus(str, Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIALLY_COMPLETED = "partially_completed"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRYING = "retrying"


class WorkflowStepSchema(BaseModel):
    """A single step in a generated workflow."""
    id: UUID
    workflow_id: UUID
    step_index: int
    title: str
    description: str
    assigned_department: str           # sales | support | research
    assigned_agent: str                # specific agent name
    input_data: Optional[Dict[str, Any]]
    output_data: Optional[Dict[str, Any]]
    status: StepStatus
    retry_count: int = 0
    latency_ms: Optional[float]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowResponse(BaseModel):
    id: UUID
    goal_id: UUID
    user_id: UUID
    status: WorkflowStatus
    steps: List[WorkflowStepSchema]
    total_steps: int
    completed_steps: int
    failed_steps: int
    total_latency_ms: Optional[float]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowListResponse(BaseModel):
    workflows: List[WorkflowResponse]
    total: int
