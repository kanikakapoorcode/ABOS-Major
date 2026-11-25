"""
Celery task definitions.

All long-running operations (agent execution, profile updates, embedding storage)
run as background tasks so the FastAPI request returns immediately.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Helper to run async code inside a Celery (sync) task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ── Helpers: update Tier-2 (aggregate) & Tier-1 (task-specific) profiles ─────

async def _recompute_rolling_stats(
    db,
    agent_name: str,
    department: Optional[str] = None,
    task_type: Optional[str] = None,
    window: int = 50,
) -> tuple[float, float, int]:
    """
    Compute rolling-window success rate, average latency (ms), and total
    executions from the executions table for either Tier-2 (aggregate) or
    Tier-1 (task-specific) scope.
    """
    from sqlalchemy import select, func, and_
    from backend.db.models.execution import Execution as ExecutionModel

    filters = [ExecutionModel.agent_name == agent_name]
    if department is not None and task_type is not None:
        filters.extend([
            ExecutionModel.department == department,
            ExecutionModel.task_type == task_type,
        ])
    where_clause = and_(*filters)

    recent_result = await db.execute(
        select(ExecutionModel.status)
        .where(where_clause)
        .order_by(ExecutionModel.created_at.desc())
        .limit(window)
    )
    statuses = [r[0] for r in recent_result.all()]
    success_rate = (
        sum(1 for s in statuses if s == "success") / len(statuses)
        if statuses
        else 0.5
    )

    # Fetch recent latencies and average in Python to avoid SQL GROUP BY errors
    lat_result = await db.execute(
        select(ExecutionModel.latency_ms)
        .where(where_clause, ExecutionModel.latency_ms.isnot(None))
        .order_by(ExecutionModel.created_at.desc())
        .limit(window)
    )
    latencies = [float(r[0]) for r in lat_result.all() if r[0] is not None]
    avg_latency = (sum(latencies) / len(latencies)) if latencies else 0.0

    total_result = await db.execute(
        select(func.count(ExecutionModel.id)).where(where_clause)
    )
    total_executions = int(total_result.scalar() or 0)
    return round(success_rate, 4), round(avg_latency, 2), total_executions


async def _upsert_agent_profiles(
    db,
    agent_name: str,
    department: str,
    task_type: Optional[str],
    execution_succeeded: bool,
    feedback_correct: Any = None,
    feedback_rating: Optional[str] = None,
    window: int = 50,
) -> tuple[float, float, Optional[str]]:
    """
    Update both Tier-2 (AgentProfile) and, when task_type is canonical,
    Tier-1 (AgentTaskProfile) in one shared helper.
    """
    from sqlalchemy import select, and_
    from backend.db.models.agent_profile import AgentProfile, AgentTaskProfile
    from backend.agents.scheduler.scoring import update_confidence_score
    from backend.agents.tasks.taxonomy import validate_task_type

    valid_task = validate_task_type(department, task_type)

    # ── Tier-2: Aggregate Profile ─────────────────────────────────────────────
    sr, avg_lat, total_execs = await _recompute_rolling_stats(
        db, agent_name=agent_name, window=window
    )
    prof_result = await db.execute(
        select(AgentProfile).where(AgentProfile.agent_name == agent_name)
    )
    profile = prof_result.scalar_one_or_none()
    curr_conf = profile.confidence_score if profile else 0.2
    new_conf = update_confidence_score(
        current_confidence=curr_conf,
        execution_succeeded=execution_succeeded,
        feedback_correct=feedback_correct,
        alpha=0.1,
        feedback_rating=feedback_rating,
    )
    if profile:
        profile.success_rate = sr
        profile.avg_latency_ms = avg_lat
        profile.confidence_score = new_conf
        profile.total_executions = total_execs
    else:
        db.add(AgentProfile(
            agent_name=agent_name,
            department=department,
            success_rate=sr,
            avg_latency_ms=avg_lat,
            confidence_score=new_conf,
            total_executions=total_execs,
            window_size=window,
        ))

    # ── Tier-1: Task-Specific Profile ─────────────────────────────────────────
    if valid_task:
        t_sr, t_avg_lat, t_total = await _recompute_rolling_stats(
            db, agent_name=agent_name, department=department, task_type=valid_task, window=window
        )
        t_res = await db.execute(
            select(AgentTaskProfile).where(
                and_(
                    AgentTaskProfile.agent_name == agent_name,
                    AgentTaskProfile.department == department,
                    AgentTaskProfile.task_type == valid_task,
                )
            )
        )
        t_profile = t_res.scalar_one_or_none()
        t_curr_conf = t_profile.confidence_score if t_profile else 0.2
        t_new_conf = update_confidence_score(
            current_confidence=t_curr_conf,
            execution_succeeded=execution_succeeded,
            feedback_correct=feedback_correct,
            alpha=0.1,
            feedback_rating=feedback_rating,
        )
        if t_profile:
            t_profile.success_rate = t_sr
            t_profile.avg_latency_ms = t_avg_lat
            t_profile.confidence_score = t_new_conf
            t_profile.total_executions = t_total
        else:
            db.add(AgentTaskProfile(
                agent_name=agent_name,
                department=department,
                task_type=valid_task,
                success_rate=t_sr,
                avg_latency_ms=t_avg_lat,
                confidence_score=t_new_conf,
                total_executions=t_total,
                window_size=window,
            ))

    return sr, new_conf, valid_task


async def _update_profiles_from_result(result: Dict[str, Any]) -> None:
    """
    After a real graph run, update Tier-2 (AgentProfile) and Tier-1
    (AgentTaskProfile) using each executed step outcome in workflow_plan.

    Runs in its own DB session after execution records are committed.
    A failure here is logged but never propagates to the caller.
    """
    from backend.db.session import AsyncSessionLocal

    plan: List[Dict[str, Any]] = result.get("workflow_plan") or []
    if not plan:
        return

    updated_agents: List[str] = []
    async with AsyncSessionLocal() as db:
        for step in plan:
            agent = step.get("assigned_agent", "")
            dept = step.get("assigned_department", "")
            step_status = step.get("status", "pending")
            if not agent or not dept or step_status == "pending":
                continue
            succeeded = step_status == "completed"
            await _upsert_agent_profiles(
                db=db,
                agent_name=agent,
                department=dept,
                task_type=step.get("task_type"),
                execution_succeeded=succeeded,
                feedback_correct=None,
            )
            if agent not in updated_agents:
                updated_agents.append(agent)

        await db.commit()
        logger.info(f"[Task] Updated aggregate & task profiles for: {updated_agents}")


# ── Shared graph run + atomic persistence helper ─────────────────────────────

async def _run_graph_and_persist(goal_id: str, workflow_id: str, goal: Any) -> None:
    """
    Execute the LangGraph workflow for an existing (goal, workflow) pair and
    persist all WorkflowStep + Execution rows, workflow summary/language fields,
    and updated agent profiles in an atomic DB transaction.
    """
    from backend.db.session import AsyncSessionLocal
    from backend.agents.graph import abos_graph
    from backend.db.models.workflow import WorkflowStep, Workflow as WorkflowModel
    from backend.db.models.execution import Execution as ExecutionModel
    from backend.services.goal_service import GoalService
    from backend.services.workflow_service import WorkflowService
    from backend.schemas.goal import GoalStatus
    from backend.schemas.workflow import WorkflowStatus
    from sqlalchemy import delete, update as sa_update

    initial_state = {
        "goal_id": goal_id,
        "workflow_id": workflow_id,
        "user_id": str(goal.user_id),
        "goal_title": goal.title,
        "goal_description": goal.description,
        "goal_priority": goal.priority,
        "goal_context": goal.context or {},
        "target_departments": goal.target_departments,
        "detected_language": None,
        "original_goal_title": None,
        "original_goal_description": None,
        "localised_summary": None,
        "localised_compliance_flags": [],
        "workflow_plan": None,
        "current_step_index": 0,
        "completed_steps": [],
        "failed_steps": [],
        "retrieved_memory": [],
        "recovery_attempts": 0,
        "max_recovery_attempts": 3,
        "compliance_plan_result": None,
        "compliance_flags": [],
        "final_status": None,
        "summary": None,
        "error": None,
        "logs": [],
    }

    try:
        result = await abos_graph.ainvoke(initial_state)
    except Exception as e:
        logger.error(f"[Task] Graph execution failed for goal {goal_id}: {e}")
        result = {"final_status": "failed", "error": str(e), "summary": None, "workflow_plan": []}

    # Persist final state to DB in a single atomic transaction
    async with AsyncSessionLocal() as db:
        goal_service = GoalService(db)
        wf_service = WorkflowService(db)

        final_status = result.get("final_status") or "failed"
        plan: List[Dict[str, Any]] = result.get("workflow_plan") or []

        # Idempotency guard: remove steps written by any prior attempt
        await db.execute(
            delete(WorkflowStep).where(WorkflowStep.workflow_id == workflow_id)
        )
        await db.flush()

        n_completed = 0
        n_failed = 0
        total_latency_ms = 0.0

        for step in plan:
            step_status = step.get("status", "pending")
            if step_status == "completed":
                n_completed += 1
            elif step_status in ("failed", "compliance_failed", "skipped", "retrying"):
                n_failed += 1

            lat = step.get("latency_ms") or 0.0
            total_latency_ms += lat

            ws = WorkflowStep(
                workflow_id=workflow_id,
                step_index=step.get("step_index", 0),
                title=str(step.get("title", ""))[:200],
                description=str(step.get("description", ""))[:1000],
                assigned_department=step.get("assigned_department", ""),
                assigned_agent=step.get("assigned_agent", ""),
                task_type=step.get("task_type"),
                input_data=step.get("input_data"),
                output_data=step.get("output_data"),
                status=step_status,
                retry_count=step.get("retry_count", 0),
                latency_ms=step.get("latency_ms"),
            )
            db.add(ws)
            await db.flush()

            exec_status = {
                "completed":         "success",
                "failed":            "failed",
                "compliance_failed": "failed",
                "skipped":           "failed",
                "retrying":          "failed",
            }.get(step_status, "failed")

            now = datetime.now(timezone.utc)
            db.add(ExecutionModel(
                workflow_step_id=ws.id,
                agent_name=step.get("assigned_agent", ""),
                department=step.get("assigned_department", ""),
                task_type=step.get("task_type"),
                status=exec_status,
                input_data=step.get("input_data"),
                output_data=step.get("output_data"),
                error_message=step.get("error_message"),
                retry_count=step.get("retry_count", 0),
                latency_ms=step.get("latency_ms"),
                scheduler_score=step.get("scheduler_score"),
                started_at=now,
                completed_at=now,
            ))

        wf_status_map = {
            "completed":           WorkflowStatus.COMPLETED,
            "failed":              WorkflowStatus.FAILED,
            "partially_completed": WorkflowStatus.PARTIALLY_COMPLETED,
            "compliance_blocked":  WorkflowStatus.FAILED,
        }
        await wf_service.update_status(
            workflow_id,
            wf_status_map.get(final_status, WorkflowStatus.FAILED),
        )
        await db.execute(
            sa_update(WorkflowModel)
            .where(WorkflowModel.id == workflow_id)
            .values(
                total_steps=len(plan),
                completed_steps=n_completed,
                failed_steps=n_failed,
                total_latency_ms=round(total_latency_ms, 2) if total_latency_ms else None,
                detected_language=result.get("detected_language"),
                summary=result.get("summary"),
                localised_summary=result.get("localised_summary"),
                compliance_flags=result.get("compliance_flags") or [],
                localised_compliance_flags=result.get("localised_compliance_flags") or [],
                error=result.get("error"),
            )
        )

        goal_status_map = {
            "completed":           GoalStatus.COMPLETED,
            "failed":              GoalStatus.FAILED,
            "partially_completed": GoalStatus.COMPLETED,
            "compliance_blocked":  GoalStatus.COMPLIANCE_BLOCKED,
        }
        await goal_service.update_status(
            goal_id,
            goal_status_map.get(final_status, GoalStatus.FAILED),
        )

        await db.commit()

    logger.info(
        f"[Task] Goal {goal_id} finished: status={final_status}, "
        f"steps={len(plan)}, completed={n_completed}, failed={n_failed}"
    )

    try:
        await _update_profiles_from_result(result)
    except Exception as prof_exc:
        logger.warning(f"[Task] Profile update skipped for goal {goal_id}: {prof_exc}")


# ── Main goal execution task ──────────────────────────────────────────────────

@celery_app.task(name="backend.workers.tasks.execute_goal_task", bind=True, max_retries=2)
def execute_goal_task(self, goal_id: str):
    """
    Main task: generate a workflow for a goal, then execute it.
    """
    async def _run():
        from backend.db.session import AsyncSessionLocal
        from backend.services.goal_service import GoalService
        from backend.services.workflow_service import WorkflowService
        from backend.schemas.goal import GoalStatus

        async with AsyncSessionLocal() as db:
            goal_service = GoalService(db)
            wf_service = WorkflowService(db)

            goal = await goal_service.get(goal_id=goal_id, user_id=None)  # type: ignore
            if not goal:
                logger.error(f"[Task] Goal {goal_id} not found.")
                return

            await goal_service.update_status(goal_id, GoalStatus.PLANNING)
            workflow = await wf_service.create(goal_id=goal_id, user_id=str(goal.user_id))
            await db.commit()

        await _run_graph_and_persist(goal_id=goal_id, workflow_id=str(workflow.id), goal=goal)

    try:
        _run_async(_run())
    except Exception as exc:
        logger.error(f"[Task] execute_goal_task failed for {goal_id}: {exc}")
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="backend.workers.tasks.execute_workflow_task", bind=True, max_retries=1)
def execute_workflow_task(self, workflow_id: str):
    """Re-execute an existing workflow (used by POST /workflows/{workflow_id}/retry)."""
    async def _run():
        from backend.db.session import AsyncSessionLocal
        from backend.services.goal_service import GoalService
        from backend.services.workflow_service import WorkflowService
        from backend.schemas.goal import GoalStatus
        from backend.schemas.workflow import WorkflowStatus

        async with AsyncSessionLocal() as db:
            wf_service = WorkflowService(db)
            goal_service = GoalService(db)

            workflow = await wf_service.get(workflow_id=workflow_id, user_id=None)
            if not workflow:
                logger.error(f"[Task] Workflow {workflow_id} not found for retry.")
                return

            goal = await goal_service.get(goal_id=str(workflow.goal_id), user_id=None)
            if not goal:
                logger.error(f"[Task] Goal {workflow.goal_id} not found for workflow {workflow_id}.")
                return

            await wf_service.update_status(workflow_id, WorkflowStatus.EXECUTING)
            await goal_service.update_status(str(goal.id), GoalStatus.EXECUTING)
            await db.commit()

        await _run_graph_and_persist(
            goal_id=str(goal.id), workflow_id=workflow_id, goal=goal
        )

    try:
        _run_async(_run())
    except Exception as exc:
        logger.error(f"[Task] execute_workflow_task failed for {workflow_id}: {exc}")
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="backend.workers.tasks.update_agent_profile_task", bind=True)
def update_agent_profile_task(self, feedback_id: str):
    """
    After feedback is submitted, recompute the affected agent's performance profile.
    This is the feedback-triggered update path (separate from the post-execution
    automatic update in _update_profiles_from_result).
    """
    async def _run():
        from sqlalchemy import select
        from backend.db.session import AsyncSessionLocal
        from backend.db.models.feedback import Feedback
        from backend.db.models.execution import Execution

        async with AsyncSessionLocal() as db:
            fb_result = await db.execute(select(Feedback).where(Feedback.id == feedback_id))
            feedback = fb_result.scalar_one_or_none()
            if not feedback:
                return

            ex_result = await db.execute(
                select(Execution).where(Execution.id == feedback.execution_id)
            )
            execution = ex_result.scalar_one_or_none()
            if not execution:
                return

            execution_succeeded = execution.status == "success"
            if feedback.rating == "correct":
                feedback_correct = True
            elif feedback.rating == "incorrect":
                feedback_correct = False
            else:
                feedback_correct = None

            sr, new_conf, valid_task = await _upsert_agent_profiles(
                db=db,
                agent_name=execution.agent_name,
                department=execution.department,
                task_type=execution.task_type,
                execution_succeeded=execution_succeeded,
                feedback_correct=feedback_correct,
                feedback_rating=feedback.rating,
            )

            await db.commit()
            logger.info(
                f"[Task] Feedback-triggered profile update for '{execution.agent_name}' "
                f"(sr={sr:.2f}, conf={new_conf:.4f}, task={valid_task})"
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
