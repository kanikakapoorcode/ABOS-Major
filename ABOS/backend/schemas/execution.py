"""
Schemas for agent task execution records.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel


class ExecutionStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RECOVERED = "recovered"   # failed then recovered via recovery module
    TIMEOUT = "timeout"


class ExecutionResponse(BaseModel):
    id: UUID
    workflow_step_id: UUID
    agent_name: str
    department: str
    status: ExecutionStatus
    input_data: Optional[Dict[str, Any]]
    output_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    retry_count: int
    latency_ms: Optional[float]
    scheduler_score: Optional[float]   # score the scheduler used to route this task
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class ExecutionListResponse(BaseModel):
    executions: list[ExecutionResponse]
    total: int
