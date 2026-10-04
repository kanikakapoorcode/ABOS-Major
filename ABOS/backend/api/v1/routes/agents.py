"""
Agents routes — query agent performance profiles used by the scheduler.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.dependencies import get_db, get_current_user_id
from backend.schemas.agent import AgentProfileResponse, AgentProfileListResponse
from backend.services.agent_service import AgentService

router = APIRouter()


@router.get("/", response_model=AgentProfileListResponse)
async def list_agents(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user_id),
):
    """
    List all registered department agents with their current
    performance profiles (success rate, avg latency, confidence score).
    """
    service = AgentService(db)
    profiles = await service.list_profiles()
    return AgentProfileListResponse(agents=profiles)


@router.get("/{agent_name}", response_model=AgentProfileResponse)
async def get_agent_profile(
    agent_name: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user_id),
):
    """Retrieve performance profile for a specific agent."""
    service = AgentService(db)
    profile = await service.get_profile(agent_name=agent_name)
    if not profile:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found.")
    return profile
