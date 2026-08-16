"""
Feedback routes — Level-2 explicit feedback memory layer.
Users and agents can submit corrections/outcomes that bias future scheduling.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.dependencies import get_db, get_current_user_id
from backend.schemas.feedback import FeedbackCreateRequest, FeedbackResponse, FeedbackListResponse
from backend.services.feedback_service import FeedbackService

router = APIRouter()


@router.post("/", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
    payload: FeedbackCreateRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """
    Submit explicit feedback for a completed execution.
    This is the primary write path for the Level-2 memory layer.
    Feedback is persisted and used to update the agent's performance profile.
    """
    service = FeedbackService(db)
    feedback = await service.create(user_id=user_id, payload=payload)
    return feedback


@router.get("/", response_model=FeedbackListResponse)
async def list_feedback(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    execution_id: str | None = None,
    skip: int = 0,
    limit: int = 20,
):
    """List feedback submitted by the current user."""
    service = FeedbackService(db)
    items = await service.list(user_id=user_id, execution_id=execution_id, skip=skip, limit=limit)
    return FeedbackListResponse(feedback=items, total=len(items))


@router.get("/{feedback_id}", response_model=FeedbackResponse)
async def get_feedback(
    feedback_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Retrieve a specific feedback entry."""
    service = FeedbackService(db)
    item = await service.get(feedback_id=str(feedback_id), user_id=user_id)
    if not item:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Feedback not found.")
    return item
