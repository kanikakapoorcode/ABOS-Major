"""
Metrics service — aggregate execution data for evaluation and dashboard charts.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.db.models.execution import Execution
from backend.db.models.goal import Goal
from backend.schemas.metrics import (
    SystemMetricsResponse,
    AgentMetricsResponse,
    AgentMetricDetail,
    RoutingAccuracyResponse,
    TimeSeriesPoint,
    RoutingAccuracyPoint,
)


class MetricsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_system_metrics(self, days: int = 30) -> SystemMetricsResponse:
        since = datetime.now(timezone.utc) - timedelta(days=days)

        # Total goals
        goals_result = await self.db.execute(
            select(func.count(Goal.id)).where(Goal.created_at >= since)
        )
        total_goals = goals_result.scalar() or 0

        # Execution stats
        exec_result = await self.db.execute(
            select(
                func.count(Execution.id),
                func.avg(Execution.latency_ms),
                func.sum(
                    func.cast(Execution.status == "success", type_=func.Integer)
                ),
            ).where(Execution.created_at >= since)
        )
        row = exec_result.one()
        total_executions = row[0] or 0
        avg_latency = float(row[1] or 0.0)
        successful = row[2] or 0

        completion_rate = (successful / total_executions) if total_executions > 0 else 0.0

        # Recovery success rate
        recovered_result = await self.db.execute(
            select(func.count(Execution.id)).where(
                Execution.status == "recovered",
                Execution.created_at >= since,
            )
        )
        failed_result = await self.db.execute(
            select(func.count(Execution.id)).where(
                Execution.status.in_(["failed", "recovered"]),
                Execution.created_at >= since,
            )
        )
        recovered = recovered_result.scalar() or 0
        total_failed = failed_result.scalar() or 0
        recovery_rate = (recovered / total_failed) if total_failed > 0 else 0.0

        return SystemMetricsResponse(
            task_completion_rate=round(completion_rate, 4),
            avg_latency_ms=round(avg_latency, 2),
            recovery_success_rate=round(recovery_rate, 4),
            total_goals=total_goals,
            total_executions=total_executions,
            period_days=days,
            completion_over_time=[],  # TODO: time-series aggregation
        )

    async def get_agent_metrics(
        self, agent_name: Optional[str], days: int = 30
    ) -> AgentMetricsResponse:
        from backend.db.models.agent_profile import AgentProfile
        query = select(AgentProfile)
        if agent_name:
            query = query.where(AgentProfile.agent_name == agent_name)
        result = await self.db.execute(query)
        profiles = result.scalars().all()

        return AgentMetricsResponse(
            agents=[
                AgentMetricDetail(
                    agent_name=p.agent_name,
                    department=p.department,
                    success_rate=p.success_rate,
                    avg_latency_ms=p.avg_latency_ms,
                    confidence_score=p.confidence_score,
                    total_executions=p.total_executions,
                )
                for p in profiles
            ],
            period_days=days,
        )

    async def get_routing_accuracy(self, days: int = 30) -> RoutingAccuracyResponse:
        # Routing accuracy = executions where feedback.suggested_agent is null
        # (i.e., no correction submitted) / total executions with feedback
        # Simplified implementation — full version uses feedback join
        return RoutingAccuracyResponse(
            overall_accuracy=0.0,
            period_days=days,
            accuracy_over_time=[],
            per_department={},
        )
