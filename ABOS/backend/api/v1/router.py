"""
Top-level API v1 router — mounts all sub-routers.
"""

from fastapi import APIRouter

from backend.api.v1.routes import auth, goals, workflows, executions, agents, metrics, feedback

api_router = APIRouter()

api_router.include_router(auth.router,       prefix="/auth",       tags=["Auth"])
api_router.include_router(goals.router,      prefix="/goals",      tags=["Goals"])
api_router.include_router(workflows.router,  prefix="/workflows",  tags=["Workflows"])
api_router.include_router(executions.router, prefix="/executions", tags=["Executions"])
api_router.include_router(agents.router,     prefix="/agents",     tags=["Agents"])
api_router.include_router(metrics.router,    prefix="/metrics",    tags=["Metrics"])
api_router.include_router(feedback.router,   prefix="/feedback",   tags=["Feedback"])
