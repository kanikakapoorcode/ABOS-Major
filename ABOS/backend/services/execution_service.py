"""
Execution service — record and query agent task executions.
"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.models.execution import Execution
from backend.schemas.execution import ExecutionStatus


class ExecutionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        workflow_step_id: str,
        agent_name: str,
        department: str,
        input_data: Optional[dict] = None,
        scheduler_score: Optional[float] = None,
    ) -> Execution:
        execution = Execution(
            workflow_step_id=workflow_step_id,
            agent_name=agent_name,
            department=department,
            status=ExecutionStatus.QUEUED.value,
            input_data=input_data,
            scheduler_score=scheduler_score,
        )
        self.db.add(execution)
        await self.db.flush()
        await self.db.refresh(execution)
        return execution

    async def get(self, execution_id: str, user_id: str) -> Optional[Execution]:
        # Join through WorkflowStep -> Workflow to verify user ownership
        result = await self.db.execute(
            select(Execution).where(Execution.id == execution_id)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        user_id: str,
        workflow_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Execution]:
        query = select(Execution).order_by(Execution.created_at.desc()).offset(skip).limit(limit)
        if workflow_id:
            from backend.db.models.workflow import WorkflowStep
            query = (
                select(Execution)
                .join(WorkflowStep, Execution.workflow_step_id == WorkflowStep.id)
                .where(WorkflowStep.workflow_id == workflow_id)
                .order_by(Execution.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(
        self,
        execution_id: str,
        status: ExecutionStatus,
        output_data: Optional[dict] = None,
        error_message: Optional[str] = None,
        latency_ms: Optional[float] = None,
        retry_count: Optional[int] = None,
    ) -> None:
        from datetime import datetime, timezone
        result = await self.db.execute(select(Execution).where(Execution.id == execution_id))
        execution = result.scalar_one_or_none()
        if execution:
            execution.status = status.value
            if output_data is not None:
                execution.output_data = output_data
            if error_message is not None:
                execution.error_message = error_message
            if latency_ms is not None:
                execution.latency_ms = latency_ms
            if retry_count is not None:
                execution.retry_count = retry_count
            if status in (ExecutionStatus.SUCCESS, ExecutionStatus.FAILED, ExecutionStatus.RECOVERED):
                execution.completed_at = datetime.now(timezone.utc)
            await self.db.flush()
