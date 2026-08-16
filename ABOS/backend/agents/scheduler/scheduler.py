"""
Performance-Based Scheduler Node — Research Contribution #2

For each workflow step produced by the planner, the scheduler:
1. Looks up all agents registered for the step's assigned department
2. Scores each agent using scoring.py
3. Assigns the highest-scoring agent to the step
4. Writes the scheduler_score back onto the step for evaluation/tracing

If only one agent exists per department (current default), the scheduler
still scores it and records the score — enabling evaluation and future
multi-agent-per-department expansion.
"""

import logging
from typing import Any, Dict, List

from backend.agents.state import ABOSState, WorkflowStepState
from backend.agents.scheduler.scoring import (
    AgentScoreInput,
    compute_score,
    select_best_agent,
)
from backend.core.config import settings

logger = logging.getLogger(__name__)


# Registry of agents per department.
# When you add a new agent variant, register it here.
# Format: department -> list of agent names
AGENT_REGISTRY: Dict[str, List[str]] = {
    "sales": ["sales_agent"],
    "support": ["support_agent"],
    "research": ["research_agent"],
}


async def _load_agent_profiles(agent_names: List[str]) -> Dict[str, AgentScoreInput]:
    """
    Load agent performance profiles from the database.
    Falls back to default cold-start values if no profile exists yet.

    Note: This function creates its own DB session since the scheduler
    runs inside Celery workers, outside of FastAPI's request lifecycle.
    """
    from backend.db.session import AsyncSessionLocal
    from backend.db.models.agent_profile import AgentProfile
    from sqlalchemy import select

    profiles: Dict[str, AgentScoreInput] = {}

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AgentProfile).where(AgentProfile.agent_name.in_(agent_names))
        )
        db_profiles = {p.agent_name: p for p in result.scalars().all()}

    for name in agent_names:
        if name in db_profiles:
            p = db_profiles[name]
            profiles[name] = AgentScoreInput(
                agent_name=p.agent_name,
                department=p.department,
                success_rate=p.success_rate,
                avg_latency_ms=p.avg_latency_ms,
                confidence_score=p.confidence_score,
                total_executions=p.total_executions,
            )
        else:
            # Cold start — agent has no execution history yet
            dept = name.replace("_agent", "")
            profiles[name] = AgentScoreInput(
                agent_name=name,
                department=dept,
                success_rate=1.0,
                avg_latency_ms=0.0,
                confidence_score=1.0,
                total_executions=0,
            )

    return profiles


async def _assign_agent(step: WorkflowStepState) -> WorkflowStepState:
    """
    Score all candidates for this step's department and assign the best one.
    Returns an updated copy of the step.
    """
    department = step["assigned_department"]
    candidates_names = AGENT_REGISTRY.get(department, [f"{department}_agent"])

    profiles = await _load_agent_profiles(candidates_names)
    candidates = list(profiles.values())

    best = select_best_agent(candidates)

    if best is None:
        logger.warning(f"[Scheduler] No candidates for department '{department}', keeping default.")
        return step

    updated_step = dict(step)
    updated_step["assigned_agent"] = best.agent_name
    updated_step["scheduler_score"] = best.composite_score

    logger.debug(
        f"[Scheduler] Step {step['step_index']} ({department}): "
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
