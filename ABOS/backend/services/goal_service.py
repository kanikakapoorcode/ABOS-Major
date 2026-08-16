"""
Goal service — CRUD operations for business goals.
"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from backend.db.models.goal import Goal
from backend.schemas.goal import GoalCreateRequest, GoalStatus


class GoalService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: str, payload: GoalCreateRequest) -> Goal:
        goal = Goal(
            user_id=user_id,
            title=payload.title,
            description=payload.description,
            priority=payload.priority.value,
            status=GoalStatus.PENDING.value,
            target_departments=payload.target_departments,
            context=payload.context,
        )
        self.db.add(goal)
        await self.db.flush()
        await self.db.refresh(goal)
        return goal

    async def get(self, goal_id: str, user_id: str) -> Optional[Goal]:
        result = await self.db.execute(
            select(Goal).where(Goal.id == goal_id, Goal.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: str, skip: int = 0, limit: int = 20) -> List[Goal]:
        result = await self.db.execute(
            select(Goal)
            .where(Goal.user_id == user_id)
            .order_by(Goal.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_status(self, goal_id: str, status: GoalStatus) -> None:
        result = await self.db.execute(select(Goal).where(Goal.id == goal_id))
        goal = result.scalar_one_or_none()
        if goal:
            goal.status = status.value
            await self.db.flush()

    async def delete(self, goal_id: str, user_id: str) -> bool:
        result = await self.db.execute(
            select(Goal).where(Goal.id == goal_id, Goal.user_id == user_id)
        )
        goal = result.scalar_one_or_none()
        if not goal:
            return False
        await self.db.delete(goal)
        await self.db.flush()
        return True
