"""
Celery application configuration.
"""

from celery import Celery
from backend.core.config import settings

celery_app = Celery(
    "abos",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["backend.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,              # re-queue if worker crashes mid-task
    worker_prefetch_multiplier=1,     # one task at a time per worker (agent tasks are heavy)
    task_routes={
        "backend.workers.tasks.execute_goal_task": {"queue": "goals"},
        "backend.workers.tasks.execute_workflow_task": {"queue": "workflows"},
        "backend.workers.tasks.update_agent_profile_task": {"queue": "profiles"},
        "backend.workers.tasks.store_feedback_embedding_task": {"queue": "memory"},
    },
)
