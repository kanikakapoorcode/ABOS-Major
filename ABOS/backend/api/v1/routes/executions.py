"""
Executions routes — track real-time and historical agent task executions.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.dependencies import get_db, get_current_user_id
from backend.schemas.execution import ExecutionResponse, ExecutionListResponse
from backend.services.execution_service import ExecutionService

router = APIRouter()


@router.get("/", response_model=ExecutionListResponse)
async def list_executions(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    workflow_id: str | None = None,
    skip: int = 0,
    limit: int = 50,
):
    """
    List executions. Optionally filter by workflow_id.
    """
    service = ExecutionService(db)
    executions = await service.list(
        user_id=user_id, workflow_id=workflow_id, skip=skip, limit=limit
    )
    return ExecutionListResponse(executions=executions, total=len(executions))


@router.get("/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """Retrieve a specific task execution record."""
    service = ExecutionService(db)
    execution = await service.get(execution_id=str(execution_id), user_id=user_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found.")
    return execution
