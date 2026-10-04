"""
Feedback service — Level-2 explicit-feedback memory layer.
Persists corrections and uses them to update agent performance profiles.
"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.models.feedback import Feedback
from backend.schemas.feedback import FeedbackCreateRequest


class FeedbackService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: str, payload: FeedbackCreateRequest) -> Feedback:
        feedback = Feedback(
            user_id=user_id,
            execution_id=str(payload.execution_id),
            rating=payload.rating.value,
            correction=payload.correction,
            suggested_agent=payload.suggested_agent,
        )
        self.db.add(feedback)
        await self.db.flush()
        await self.db.refresh(feedback)

        # Trigger async profile update via Celery
        from backend.workers.tasks import update_agent_profile_task
        update_agent_profile_task.delay(str(feedback.id))

        return feedback

    async def get(self, feedback_id: str, user_id: str) -> Optional[Feedback]:
        result = await self.db.execute(
            select(Feedback).where(
                Feedback.id == feedback_id, Feedback.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        user_id: str,
        execution_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> List[Feedback]:
        query = (
            select(Feedback)
            .where(Feedback.user_id == user_id)
            .order_by(Feedback.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        if execution_id:
            query = query.where(Feedback.execution_id == execution_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())
