"""
Schemas for metrics and evaluation endpoints.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel


class TimeSeriesPoint(BaseModel):
    date: str
    value: float


class SystemMetricsResponse(BaseModel):
    task_completion_rate: float
    avg_latency_ms: float
    recovery_success_rate: float
    total_goals: int
    total_executions: int
    period_days: int
    completion_over_time: List[TimeSeriesPoint]


class AgentMetricDetail(BaseModel):
    agent_name: str
    department: str
    success_rate: float
    avg_latency_ms: float
    confidence_score: float
    total_executions: int


class AgentMetricsResponse(BaseModel):
    agents: List[AgentMetricDetail]
    period_days: int


class RoutingAccuracyPoint(BaseModel):
    date: str
    accuracy: float
    total_routed: int


class RoutingAccuracyResponse(BaseModel):
    overall_accuracy: float
    period_days: int
    accuracy_over_time: List[RoutingAccuracyPoint]
    per_department: Dict[str, float]
