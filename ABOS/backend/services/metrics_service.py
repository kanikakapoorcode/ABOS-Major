"""
Metrics service — aggregate execution data for evaluation and dashboard charts.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, cast, Date

from backend.db.models.execution import Execution
from backend.db.models.feedback import Feedback
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
        success_expr = func.sum(case((Execution.status == "success", 1), else_=0))
        exec_result = await self.db.execute(
            select(
                func.count(Execution.id),
                func.avg(Execution.latency_ms),
                success_expr,
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

        # Daily completion rate series
        day_col = cast(Execution.created_at, Date)
        daily_result = await self.db.execute(
            select(
                day_col.label("day"),
                func.count(Execution.id).label("total"),
                success_expr.label("succ"),
            )
            .where(Execution.created_at >= since)
            .group_by(day_col)
            .order_by(day_col)
        )
        completion_over_time = [
            TimeSeriesPoint(
                date=str(r.day),
                value=round((r.succ or 0) / r.total, 4) if r.total else 0.0,
            )
            for r in daily_result.all()
        ]

        return SystemMetricsResponse(
            task_completion_rate=round(completion_rate, 4),
            avg_latency_ms=round(avg_latency, 2),
            recovery_success_rate=round(recovery_rate, 4),
            total_goals=total_goals,
            total_executions=total_executions,
            period_days=days,
            completion_over_time=completion_over_time,
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
        """
        Routing accuracy computed from feedback joined with execution records:
        an execution is counted as correctly routed when feedback.rating == 'correct'
        and no different suggested_agent was specified.
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (
            await self.db.execute(
                select(
                    Feedback.created_at,
                    Feedback.rating,
                    Feedback.suggested_agent,
                    Execution.agent_name,
                    Execution.department,
                )
                .join(Execution, Feedback.execution_id == Execution.id)
                .where(Feedback.created_at >= since)
                .order_by(Feedback.created_at)
            )
        ).all()

        if not rows:
            return RoutingAccuracyResponse(
                overall_accuracy=0.0,
                period_days=days,
                accuracy_over_time=[],
                per_department={},
            )

        total = len(rows)
        correct_total = 0
        dept_counts: Dict[str, list[int]] = {}
        day_counts: Dict[str, list[int]] = {}

        for created_at, rating, suggested_agent, agent_name, department in rows:
            is_correct = int(
                rating == "correct"
                and (not suggested_agent or suggested_agent == agent_name)
            )
            correct_total += is_correct
            dept_bucket = dept_counts.setdefault(department, [0, 0])
            dept_bucket[0] += is_correct
            dept_bucket[1] += 1

            day_key = created_at.date().isoformat()
            day_bucket = day_counts.setdefault(day_key, [0, 0])
            day_bucket[0] += is_correct
            day_bucket[1] += 1

        return RoutingAccuracyResponse(
            overall_accuracy=round(correct_total / total, 4),
            period_days=days,
            accuracy_over_time=[
                RoutingAccuracyPoint(
                    date=day,
                    accuracy=round(corr / cnt, 4),
                    total_routed=cnt,
                )
                for day, (corr, cnt) in sorted(day_counts.items())
            ],
            per_department={
                dept: round(corr / cnt, 4)
                for dept, (corr, cnt) in dept_counts.items()
            },
        )
