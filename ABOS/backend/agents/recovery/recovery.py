"""
Recovery Module — LangGraph Node

Adopted from Self-Healing Agentic Orchestrators (2026) — cited, not claimed as novel.
Reference: arxiv 2606.01416

Handles: failure detection, classification, and bounded retry/reroute logic.
"""

import logging
from typing import Any, Dict

from backend.agents.state import ABOSState, WorkflowStepState
from backend.agents.recovery.classifier import (
    classify_failure,
    decide_recovery_action,
    FailureType,
    RecoveryAction,
)
from backend.agents.scheduler.scheduler import AGENT_REGISTRY

logger = logging.getLogger(__name__)


def _has_alternative_agent(department: str, current_agent: str) -> bool:
    """Check if there is another agent available in this department."""
    agents = AGENT_REGISTRY.get(department, [])
    return any(a != current_agent for a in agents)


async def recovery_node(state: ABOSState) -> Dict[str, Any]:
    """
    LangGraph node: Recovery.

    Called when the executor reports a step failure.
    Classifies the failure, decides the action, and updates state accordingly.

    Reads:  workflow_plan, current_step_index, recovery_attempts, max_recovery_attempts
    Writes: workflow_plan (updated step), current_step_index, recovery_attempts,
            failed_steps (if unrecoverable), logs
    """
    plan = state.get("workflow_plan") or []
    step_idx = state.get("current_step_index", 0)
    recovery_attempts = state.get("recovery_attempts", 0)
    max_attempts = state.get("max_recovery_attempts", 3)

    if step_idx >= len(plan):
        return {"logs": ["Recovery: no current step to recover."]}

    current_step: WorkflowStepState = dict(plan[step_idx])
    error_msg = current_step.get("error_message") or "Unknown error"
    retry_count = current_step.get("retry_count", 0)

    failure_type = classify_failure(error_msg, retry_count, max_attempts)
    has_alt = _has_alternative_agent(
        current_step["assigned_department"],
        current_step["assigned_agent"],
    )
    action = decide_recovery_action(failure_type, retry_count, max_attempts, has_alt)

    logger.info(
        f"[Recovery] Step {step_idx} ('{current_step['title']}'): "
        f"failure_type={failure_type}, action={action}, "
        f"retry={retry_count}/{max_attempts}"
    )

    updated_plan = list(plan)
    log_messages = [
        f"Recovery: step {step_idx} — type={failure_type}, action={action}."
    ]

    if action == RecoveryAction.RETRY or action == RecoveryAction.RETRY_WITH_TIMEOUT:
        current_step["status"] = "retrying"
        current_step["retry_count"] = retry_count + 1
        updated_plan[step_idx] = current_step
        return {
            "workflow_plan": updated_plan,
            "recovery_attempts": recovery_attempts + 1,
            "logs": log_messages,
        }

    elif action == RecoveryAction.REROUTE:
        # Find an alternative agent in the same department
        dept_agents = AGENT_REGISTRY.get(current_step["assigned_department"], [])
        alternatives = [a for a in dept_agents if a != current_step["assigned_agent"]]
        if alternatives:
            current_step["assigned_agent"] = alternatives[0]
            current_step["status"] = "retrying"
            current_step["retry_count"] = retry_count + 1
            updated_plan[step_idx] = current_step
            log_messages.append(
                f"Recovery: rerouted step {step_idx} to '{alternatives[0]}'."
            )
        else:
            # No alternative — skip
            current_step["status"] = "failed"
            updated_plan[step_idx] = current_step
        return {
            "workflow_plan": updated_plan,
            "recovery_attempts": recovery_attempts + 1,
            "logs": log_messages,
        }

    else:
        # SKIP — mark step as failed, advance to next step
        current_step["status"] = "failed"
        updated_plan[step_idx] = current_step
        log_messages.append(f"Recovery: step {step_idx} marked failed, skipping.")
        return {
            "workflow_plan": updated_plan,
            "failed_steps": [current_step],
            "current_step_index": step_idx + 1,
            "recovery_attempts": 0,  # reset for next step
            "logs": log_messages,
        }
