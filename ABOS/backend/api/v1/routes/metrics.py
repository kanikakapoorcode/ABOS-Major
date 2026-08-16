"""
Metrics routes — aggregate performance data for evaluation and dashboard charts.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from backend.core.dependencies import get_db, get_current_user_id
from backend.schemas.metrics import (
    SystemMetricsResponse,
    AgentMetricsResponse,
    RoutingAccuracyResponse,
)
from backend.services.metrics_service import MetricsService

router = APIRouter()


@router.get("/system", response_model=SystemMetricsResponse)
async def get_system_metrics(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user_id),
    days: int = Query(default=30, ge=1, le=365),
):
    """
    Overall system metrics: task completion rate, avg latency,
    recovery success rate — for the past N days.
    """
    service = MetricsService(db)
    return await service.get_system_metrics(days=days)


@router.get("/agents", response_model=AgentMetricsResponse)
async def get_agent_metrics(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user_id),
    agent_name: Optional[str] = None,
    days: int = Query(default=30, ge=1, le=365),
):
    """
    Per-agent performance breakdown: success rate, latency, confidence.
    Optionally filter by agent_name.
    """
    service = MetricsService(db)
    return await service.get_agent_metrics(agent_name=agent_name, days=days)


@router.get("/routing", response_model=RoutingAccuracyResponse)
async def get_routing_accuracy(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user_id),
    days: int = Query(default=30, ge=1, le=365),
):
    """
    Scheduler routing accuracy over time — used to evaluate the
    performance-based scheduling policy.
    """
    service = MetricsService(db)
    return await service.get_routing_accuracy(days=days)
