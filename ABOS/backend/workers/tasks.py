"""
Celery task definitions.

All long-running operations (agent execution, profile updates, embedding storage)
run as background tasks so the FastAPI request returns immediately.
"""

import asyncio
import logging

from backend.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Helper to run async code inside a Celery (sync) task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="backend.workers.tasks.execute_goal_task", bind=True, max_retries=2)
def execute_goal_task(self, goal_id: str):
    """
    Main task: generate a workflow for a goal, then execute it.
    1. Load the goal from DB
    2. Create a Workflow record
    3. Run the LangGraph graph
    4. Persist results back to DB
    """
    async def _run():
        from backend.db.session import AsyncSessionLocal
        from backend.services.goal_service import GoalService
        from backend.services.workflow_service import WorkflowService
        from backend.agents.graph import abos_graph
        from backend.schemas.goal import GoalStatus
        from backend.schemas.workflow import WorkflowStatus

        async with AsyncSessionLocal() as db:
            goal_service = GoalService(db)
            wf_service = WorkflowService(db)

            goal = await goal_service.get(goal_id=goal_id, user_id=None)  # type: ignore
            if not goal:
                logger.error(f"[Task] Goal {goal_id} not found.")
                return

            await goal_service.update_status(goal_id, GoalStatus.PLANNING)

            # Create workflow record
            workflow = await wf_service.create(goal_id=goal_id, user_id=str(goal.user_id))
            await db.commit()

        # Run the LangGraph graph (outside DB session — graph manages its own sessions)
        initial_state = {
            "goal_id": goal_id,
            "workflow_id": str(workflow.id),
            "user_id": str(goal.user_id),
            "goal_title": goal.title,
            "goal_description": goal.description,
            "goal_priority": goal.priority,
            "goal_context": goal.context or {},
            "target_departments": goal.target_departments,
            "workflow_plan": None,
            "current_step_index": 0,
            "completed_steps": [],
            "failed_steps": [],
            "retrieved_memory": [],
            "recovery_attempts": 0,
            "max_recovery_attempts": 3,
            "final_status": None,
            "summary": None,
            "error": None,
            "logs": [],
        }

        try:
            result = await abos_graph.ainvoke(initial_state)
        except Exception as e:
            logger.error(f"[Task] Graph execution failed for goal {goal_id}: {e}")
            result = {"final_status": "failed", "error": str(e), "summary": None}

        # Persist final state back to DB
        async with AsyncSessionLocal() as db:
            goal_service = GoalService(db)
            wf_service = WorkflowService(db)

            final_status = result.get("final_status", "failed")
            goal_status = GoalStatus.COMPLETED if final_status == "completed" else (
                GoalStatus.FAILED if final_status == "failed" else GoalStatus.COMPLETED
            )
            await goal_service.update_status(goal_id, goal_status)

            wf_status_map = {
                "completed": WorkflowStatus.COMPLETED,
                "failed": WorkflowStatus.FAILED,
                "partially_completed": WorkflowStatus.PARTIALLY_COMPLETED,
            }
            await wf_service.update_status(
                str(workflow.id),
                wf_status_map.get(final_status, WorkflowStatus.FAILED),
            )
            await db.commit()

        logger.info(f"[Task] Goal {goal_id} finished with status: {final_status}")

    try:
        _run_async(_run())
    except Exception as exc:
        logger.error(f"[Task] execute_goal_task failed for {goal_id}: {exc}")
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="backend.workers.tasks.execute_workflow_task", bind=True, max_retries=1)
def execute_workflow_task(self, workflow_id: str):
    """Re-execute an existing workflow (used by the retry endpoint)."""
    logger.info(f"[Task] Re-executing workflow {workflow_id}")
    # TODO: load workflow, rebuild state, reinvoke graph from current position
    pass


@celery_app.task(name="backend.workers.tasks.update_agent_profile_task", bind=True)
def update_agent_profile_task(self, feedback_id: str):
    """
    After feedback is submitted, recompute the affected agent's performance profile.
    """
    async def _run():
        from backend.db.session import AsyncSessionLocal
        from backend.db.models.feedback import Feedback
        from backend.db.models.execution import Execution
        from backend.db.models.agent_profile import AgentProfile
        from backend.agents.scheduler.scoring import update_confidence_score
        from sqlalchemy import select, func

        async with AsyncSessionLocal() as db:
            from backend.db.models.agent_profile import AgentTaskProfile
            from backend.agents.tasks.taxonomy import validate_task_type
            from sqlalchemy import and_

            # Load feedback
            fb_result = await db.execute(select(Feedback).where(Feedback.id == feedback_id))
            feedback = fb_result.scalar_one_or_none()
            if not feedback:
                return

            # Load execution
            ex_result = await db.execute(
                select(Execution).where(Execution.id == feedback.execution_id)
            )
            execution = ex_result.scalar_one_or_none()
            if not execution:
                return

            agent_name = execution.agent_name
            department = execution.department
            task_type = validate_task_type(department, execution.task_type)
            execution_succeeded = execution.status == "success"
            feedback_correct = feedback.rating == "correct" if feedback.rating else None

            window = 50

            # ── 1. Aggregate Profile Computation ──────────────────────────────
            recent = await db.execute(
                select(Execution.status)
                .where(Execution.agent_name == agent_name)
                .order_by(Execution.created_at.desc())
                .limit(window)
            )
            statuses = [r[0] for r in recent.all()]
            success_count = sum(1 for s in statuses if s == "success")
            success_rate = success_count / len(statuses) if statuses else 0.5

            lat_result = await db.execute(
                select(func.avg(Execution.latency_ms))
                .where(
                    Execution.agent_name == agent_name,
                    Execution.latency_ms.isnot(None),
                )
                .order_by(Execution.created_at.desc())
                .limit(window)
            )
            avg_latency = float(lat_result.scalar() or 0.0)

            profile_result = await db.execute(
                select(AgentProfile).where(AgentProfile.agent_name == agent_name)
            )
            profile = profile_result.scalar_one_or_none()

            current_confidence = profile.confidence_score if profile else 0.2
            new_confidence = update_confidence_score(
                current_confidence, execution_succeeded, feedback_correct
            )

            total = await db.execute(
                select(func.count(Execution.id)).where(Execution.agent_name == agent_name)
            )
            total_executions = total.scalar() or 0

            if profile:
                profile.success_rate = round(success_rate, 4)
                profile.avg_latency_ms = round(avg_latency, 2)
                profile.confidence_score = new_confidence
                profile.total_executions = total_executions
            else:
                new_profile = AgentProfile(
                    agent_name=agent_name,
                    department=department,
                    success_rate=round(success_rate, 4),
                    avg_latency_ms=round(avg_latency, 2),
                    confidence_score=new_confidence,
                    total_executions=total_executions,
                    window_size=window,
                )
                db.add(new_profile)

            # ── 2. Task-Specific Profile Computation (if valid task_type) ─────
            if task_type:
                task_recent = await db.execute(
                    select(Execution.status)
                    .where(
                        and_(
                            Execution.agent_name == agent_name,
                            Execution.department == department,
                            Execution.task_type == task_type,
                        )
                    )
                    .order_by(Execution.created_at.desc())
                    .limit(window)
                )
                task_statuses = [r[0] for r in task_recent.all()]
                task_succ_count = sum(1 for s in task_statuses if s == "success")
                task_success_rate = task_succ_count / len(task_statuses) if task_statuses else 0.5

                task_lat_result = await db.execute(
                    select(func.avg(Execution.latency_ms))
                    .where(
                        and_(
                            Execution.agent_name == agent_name,
                            Execution.department == department,
                            Execution.task_type == task_type,
                            Execution.latency_ms.isnot(None),
                        )
                    )
                    .order_by(Execution.created_at.desc())
                    .limit(window)
                )
                task_avg_latency = float(task_lat_result.scalar() or 0.0)

                task_profile_result = await db.execute(
                    select(AgentTaskProfile).where(
                        and_(
                            AgentTaskProfile.agent_name == agent_name,
                            AgentTaskProfile.department == department,
                            AgentTaskProfile.task_type == task_type,
                        )
                    )
                )
                task_profile = task_profile_result.scalar_one_or_none()

                task_curr_conf = task_profile.confidence_score if task_profile else 0.2
                task_new_conf = update_confidence_score(
                    task_curr_conf, execution_succeeded, feedback_correct
                )

                task_total_res = await db.execute(
                    select(func.count(Execution.id)).where(
                        and_(
                            Execution.agent_name == agent_name,
                            Execution.department == department,
                            Execution.task_type == task_type,
                        )
                    )
                )
                task_total_execs = task_total_res.scalar() or 0

                if task_profile:
                    task_profile.success_rate = round(task_success_rate, 4)
                    task_profile.avg_latency_ms = round(task_avg_latency, 2)
                    task_profile.confidence_score = task_new_conf
                    task_profile.total_executions = task_total_execs
                else:
                    new_task_profile = AgentTaskProfile(
                        agent_name=agent_name,
                        department=department,
                        task_type=task_type,
                        success_rate=round(task_success_rate, 4),
                        avg_latency_ms=round(task_avg_latency, 2),
                        confidence_score=task_new_conf,
                        total_executions=task_total_execs,
                        window_size=window,
                    )
                    db.add(new_task_profile)

            # Atomic commit of both aggregate and task-specific profiles
            await db.commit()
            logger.info(
                f"[Task] Transactionally updated profiles for '{agent_name}' "
                f"(Aggregate: sr={success_rate:.2f}, lat={avg_latency:.0f}ms; "
                f"Task '{task_type}': {'updated' if task_type else 'none'})"
            )

    _run_async(_run())


@celery_app.task(name="backend.workers.tasks.store_feedback_embedding_task")
def store_feedback_embedding_task(feedback_id: str, correction_text: str):
    """
    Compute and store the embedding for a feedback correction (Level-2 memory layer).
    """
    async def _run():
        from backend.agents.memory.memory import store_feedback_embedding
        await store_feedback_embedding(feedback_id, correction_text)

    _run_async(_run())
