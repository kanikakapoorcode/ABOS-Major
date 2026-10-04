"""
Custom application exceptions and FastAPI exception handlers.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class ABOSException(Exception):
    """Base exception for all ABOS errors."""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class GoalNotFoundException(ABOSException):
    def __init__(self, goal_id: str):
        super().__init__(f"Goal '{goal_id}' not found.", status_code=404)


class WorkflowNotFoundException(ABOSException):
    def __init__(self, workflow_id: str):
        super().__init__(f"Workflow '{workflow_id}' not found.", status_code=404)


class AgentExecutionError(ABOSException):
    def __init__(self, agent: str, reason: str):
        super().__init__(f"Agent '{agent}' failed: {reason}", status_code=500)


class SchedulerError(ABOSException):
    def __init__(self, reason: str):
        super().__init__(f"Scheduler error: {reason}", status_code=500)


class AuthenticationError(ABOSException):
    def __init__(self, reason: str = "Invalid credentials"):
        super().__init__(reason, status_code=401)


class PermissionDeniedError(ABOSException):
    def __init__(self):
        super().__init__("Permission denied.", status_code=403)


# ── Register handlers ─────────────────────────────────────────────────────────

def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ABOSException)
    async def abos_exception_handler(request: Request, exc: ABOSException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred."},
        )
