"""
Workflows routes — retrieve generated workflows, steps, and execution state.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.dependencies import get_db, get_current_user_id
from backend.schemas.workflow import WorkflowResponse, WorkflowListResponse
from backend.services.workflow_service import WorkflowService

router = APIRouter()


@router.get("/", response_model=WorkflowListResponse)
async def list_workflows(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    skip: int = 0,
    limit: int = 20,
):
    """List all generated workflows for the current user."""
    service = WorkflowService(db)
    workflows = await service.list_by_user(user_id=user_id, skip=skip, limit=limit)
    return WorkflowListResponse(workflows=workflows, total=len(workflows))


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Retrieve a specific workflow with all its steps."""
    service = WorkflowService(db)
    workflow = await service.get(workflow_id=str(workflow_id), user_id=user_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    return workflow


@router.post("/{workflow_id}/retry")
async def retry_workflow(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Re-trigger execution of a failed or incomplete workflow."""
    from backend.workers.tasks import execute_workflow_task
    service = WorkflowService(db)
    workflow = await service.get(workflow_id=str(workflow_id), user_id=user_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found.")
    execute_workflow_task.delay(str(workflow_id))
    return {"detail": "Workflow re-queued for execution.", "workflow_id": str(workflow_id)}
