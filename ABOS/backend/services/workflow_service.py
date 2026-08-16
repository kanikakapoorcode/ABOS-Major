"""
Workflow service — CRUD operations for generated workflows and steps.
"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.db.models.workflow import Workflow, WorkflowStep
from backend.schemas.workflow import WorkflowStatus


class WorkflowService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, goal_id: str, user_id: str) -> Workflow:
        workflow = Workflow(
            goal_id=goal_id,
            user_id=user_id,
            status=WorkflowStatus.PENDING.value,
        )
        self.db.add(workflow)
        await self.db.flush()
        await self.db.refresh(workflow)
        return workflow

    async def get(self, workflow_id: str, user_id: str) -> Optional[Workflow]:
        result = await self.db.execute(
            select(Workflow)
            .options(selectinload(Workflow.steps))
            .where(Workflow.id == workflow_id, Workflow.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: str, skip: int = 0, limit: int = 20) -> List[Workflow]:
        result = await self.db.execute(
            select(Workflow)
            .options(selectinload(Workflow.steps))
            .where(Workflow.user_id == user_id)
            .order_by(Workflow.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_status(self, workflow_id: str, status: WorkflowStatus) -> None:
        result = await self.db.execute(select(Workflow).where(Workflow.id == workflow_id))
        workflow = result.scalar_one_or_none()
        if workflow:
            workflow.status = status.value
            await self.db.flush()

    async def add_steps(self, workflow_id: str, steps: List[dict]) -> List[WorkflowStep]:
        """
        Bulk-insert generated workflow steps.
        Each dict must contain: step_index, title, description,
        assigned_department, assigned_agent, input_data.
        """
        created = []
        for s in steps:
            step = WorkflowStep(workflow_id=workflow_id, **s)
            self.db.add(step)
            created.append(step)
        await self.db.flush()
        return created
