"""
Goals routes — submit a business goal, retrieve goals and their status.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.dependencies import get_db, get_current_user_id
from backend.schemas.goal import GoalCreateRequest, GoalResponse, GoalListResponse
from backend.services.goal_service import GoalService
from backend.workers.tasks import execute_goal_task

router = APIRouter()


@router.post("/", response_model=GoalResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_goal(
    payload: GoalCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Submit a high-level business goal.
    Returns the created goal immediately; workflow generation runs asynchronously.
    """
    service = GoalService(db)
    goal = await service.create(user_id=user_id, payload=payload)

    # Dispatch async workflow generation via Celery
    execute_goal_task.delay(str(goal.id))

    return goal


@router.get("/", response_model=GoalListResponse)
async def list_goals(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    skip: int = 0,
    limit: int = 20,
):
    """List all goals submitted by the current user."""
    service = GoalService(db)
    goals = await service.list_by_user(user_id=user_id, skip=skip, limit=limit)
    return GoalListResponse(goals=goals, total=len(goals))


@router.get("/{goal_id}", response_model=GoalResponse)
async def get_goal(
    goal_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Retrieve a specific goal by ID."""
    service = GoalService(db)
    goal = await service.get(goal_id=str(goal_id), user_id=user_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found.")
    return goal


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    goal_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Delete a goal and its associated workflows."""
    service = GoalService(db)
    deleted = await service.delete(goal_id=str(goal_id), user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Goal not found.")
