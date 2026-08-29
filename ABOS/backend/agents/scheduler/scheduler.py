"""
Performance-Based Scheduler Node — Research Contribution #2

For each workflow step produced by the planner, the scheduler:
1. Looks up all agents registered for the step's assigned department
2. Evaluates evidence under a 3-tier sufficiency-aware hierarchy:
     Tier 1: Task-Specific Profile (AgentTaskProfile) if total_executions >= MIN_TASK_EVIDENCE (3)
     Tier 2: Aggregate Agent Profile (AgentProfile) if total_executions >= MIN_AGGREGATE_EVIDENCE (1)
     Tier 3: Cold-Start Prior (0.41)
3. Scores each agent using scoring.py
4. Assigns the highest-scoring agent to the step
5. Writes the scheduler_score back onto the step for evaluation/tracing
"""

import logging
from typing import Any, Dict, List, Optional

from backend.agents.state import ABOSState, WorkflowStepState
from backend.agents.tasks.taxonomy import (
    MIN_TASK_EVIDENCE,
    MIN_AGGREGATE_EVIDENCE,
    validate_task_type,
)
from backend.agents.scheduler.scoring import (
    AgentScoreInput,
    compute_score,
    select_best_agent,
)
from backend.core.config import settings

logger = logging.getLogger(__name__)


# Registry of agents per department.
# Primary candidate is listed first for deterministic cold-start tie-breaking.
# Format: department -> list of agent candidate names
AGENT_REGISTRY: Dict[str, List[str]] = {
    "sales": ["sales_outreach_fast", "sales_enterprise_thorough"],
    "support": ["support_tier1_fast", "support_tier2_specialist"],
    "research": ["research_kpi_quick", "research_deep_analyst"],
}


async def _load_agent_profiles(
    agent_names: List[str],
    department: str,
    task_type: Optional[str] = None,
) -> Dict[str, AgentScoreInput]:
    """
    Load agent performance profiles following the 3-tier evidence hierarchy:
      - Tier 1: Task-Specific (AgentTaskProfile) if task_type is known & total_executions >= 3
      - Tier 2: Aggregate (AgentProfile) if total_executions >= 1
      - Tier 3: Cold-Start Prior (composite score 0.41) if no sufficient history

    Note: This function creates its own DB session since the scheduler
    runs inside Celery workers, outside of FastAPI's request lifecycle.
    """
    from backend.db.session import AsyncSessionLocal
    from backend.db.models.agent_profile import AgentProfile, AgentTaskProfile
    from sqlalchemy import select, and_

    profiles: Dict[str, AgentScoreInput] = {}
    valid_task = validate_task_type(department, task_type)

    async with AsyncSessionLocal() as session:
        # 1. Fetch aggregate profiles
        agg_result = await session.execute(
            select(AgentProfile).where(AgentProfile.agent_name.in_(agent_names))
        )
        agg_profiles = {p.agent_name: p for p in agg_result.scalars().all()}

        # 2. Fetch task-specific profiles if canonical task_type is present
        task_profiles = {}
        if valid_task:
            task_result = await session.execute(
                select(AgentTaskProfile).where(
                    and_(
                        AgentTaskProfile.agent_name.in_(agent_names),
                        AgentTaskProfile.department == department,
                        AgentTaskProfile.task_type == valid_task,
                    )
                )
            )
            task_profiles = {p.agent_name: p for p in task_result.scalars().all()}

    for name in agent_names:
        # ── Tier 1: Task-Specific Profile (with sufficiency check) ────────────
        if name in task_profiles and task_profiles[name].total_executions >= MIN_TASK_EVIDENCE:
            tp = task_profiles[name]
            profiles[name] = AgentScoreInput(
                agent_name=tp.agent_name,
                department=tp.department,
                success_rate=tp.success_rate,
                avg_latency_ms=tp.avg_latency_ms,
                confidence_score=tp.confidence_score,
                total_executions=tp.total_executions,
            )
            logger.debug(
                f"[Scheduler Evidence] Used Tier-1 (Task-Specific: {valid_task}) for '{name}' "
                f"(N={tp.total_executions}, SR={tp.success_rate:.2f})"
            )
            continue

        # ── Tier 2: Aggregate Profile Fallback (with sufficiency check) ───────
        if name in agg_profiles and agg_profiles[name].total_executions >= MIN_AGGREGATE_EVIDENCE:
            ap = agg_profiles[name]
            profiles[name] = AgentScoreInput(
                agent_name=ap.agent_name,
                department=ap.department,
                success_rate=ap.success_rate,
                avg_latency_ms=ap.avg_latency_ms,
                confidence_score=ap.confidence_score,
                total_executions=ap.total_executions,
            )
            logger.debug(
                f"[Scheduler Evidence] Used Tier-2 (Aggregate) for '{name}' "
                f"(N={ap.total_executions}, SR={ap.success_rate:.2f})"
            )
            continue

        # ── Tier 3: Cold-Start Prior (No sufficient empirical evidence) ───────
        profiles[name] = AgentScoreInput(
            agent_name=name,
            department=department,
            success_rate=0.5,
            avg_latency_ms=0.0,
            confidence_score=0.2,
            total_executions=0,
        )
        logger.debug(f"[Scheduler Evidence] Used Tier-3 (Cold-Start Prior 0.41) for '{name}'")

    return profiles


async def _assign_agent(step: WorkflowStepState) -> WorkflowStepState:
    """
    Score all candidates for this step's department and assign the best one.
    Returns an updated copy of the step.
    """
    department = step["assigned_department"]
    task_type = step.get("task_type")
    candidates_names = AGENT_REGISTRY.get(department, [f"{department}_agent"])

    profiles = await _load_agent_profiles(candidates_names, department=department, task_type=task_type)
    candidates = list(profiles.values())

    best = select_best_agent(candidates)

    if best is None:
        logger.warning(f"[Scheduler] No candidates for department '{department}', keeping default.")
        return step

    updated_step = dict(step)
    updated_step["assigned_agent"] = best.agent_name
    updated_step["scheduler_score"] = best.composite_score

    logger.debug(
        f"[Scheduler] Step {step['step_index']} ({department}/{task_type}): "
        f"assigned '{best.agent_name}' with score {best.composite_score:.4f} "
        f"(sr={best.success_rate:.2f}, lat={best.latency_score:.2f}, conf={best.confidence_score:.2f})"
    )

    return updated_step


async def scheduler_node(state: ABOSState) -> Dict[str, Any]:
    """
    LangGraph node: Performance-Based Scheduler.

    Reads:  workflow_plan
    Writes: workflow_plan (with assigned_agent and scheduler_score populated), logs
    """
    plan = state.get("workflow_plan") or []
    if not plan:
        logger.warning("[Scheduler] No workflow plan to schedule.")
        return {"logs": ["Scheduler: no steps to schedule."]}

    logger.info(f"[Scheduler] Scheduling {len(plan)} steps for goal_id={state['goal_id']}")

    scheduled_plan = []
    for step in plan:
        assigned_step = await _assign_agent(step)
        scheduled_plan.append(assigned_step)

    return {
        "workflow_plan": scheduled_plan,
        "logs": [f"Scheduler assigned agents to {len(scheduled_plan)} steps."],
    }
