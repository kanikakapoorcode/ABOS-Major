"""
Agent service — query and update agent performance profiles.
"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.models.agent_profile import AgentProfile


class AgentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_profiles(self) -> List[AgentProfile]:
        result = await self.db.execute(
            select(AgentProfile).order_by(AgentProfile.department, AgentProfile.agent_name)
        )
        return list(result.scalars().all())

    async def get_profile(self, agent_name: str) -> Optional[AgentProfile]:
        result = await self.db.execute(
            select(AgentProfile).where(AgentProfile.agent_name == agent_name)
        )
        return result.scalar_one_or_none()

    async def upsert_profile(
        self,
        agent_name: str,
        department: str,
        success_rate: float,
        avg_latency_ms: float,
        confidence_score: float,
        total_executions: int,
        window_size: int,
    ) -> AgentProfile:
        from datetime import datetime, timezone
        profile = await self.get_profile(agent_name)
        if profile:
            profile.success_rate = success_rate
            profile.avg_latency_ms = avg_latency_ms
            profile.confidence_score = confidence_score
            profile.total_executions = total_executions
            profile.window_size = window_size
            profile.last_updated = datetime.now(timezone.utc)
        else:
            profile = AgentProfile(
                agent_name=agent_name,
                department=department,
                success_rate=success_rate,
                avg_latency_ms=avg_latency_ms,
                confidence_score=confidence_score,
                total_executions=total_executions,
                window_size=window_size,
            )
            self.db.add(profile)
        await self.db.flush()
        await self.db.refresh(profile)
        return profile
