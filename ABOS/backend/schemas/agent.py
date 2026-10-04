"""
Schemas for agent performance profiles.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class AgentProfileResponse(BaseModel):
    agent_name: str
    department: str
    success_rate: float         # rolling window success rate (0.0–1.0)
    avg_latency_ms: float       # rolling average latency
    confidence_score: float     # composite scheduler score (0.0–1.0)
    total_executions: int
    window_size: int            # number of recent executions used for scoring
    last_updated: Optional[datetime]

    model_config = {"from_attributes": True}


class AgentProfileListResponse(BaseModel):
    agents: List[AgentProfileResponse]
