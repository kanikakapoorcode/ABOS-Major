"""
Executor and Summarizer Nodes

executor_node: Runs the current workflow step via the assigned department agent.
summarizer_node: Generates a natural-language summary of the completed run.
"""

import logging
from typing import Any, Dict

from litellm import acompletion

from backend.agents.state import ABOSState, WorkflowStepState
from backend.agents.planner.prompts import SUMMARIZER_SYSTEM_PROMPT, SUMMARIZER_USER_PROMPT
from backend.core.config import settings

logger = logging.getLogger(__name__)

# Agent registry — maps agent name to instance
# Imported lazily to avoid circular imports at module load time
def _get_agent_registry():
    from backend.agents.department.sales import sales_agent
    from backend.agents.department.support import support_agent
    from backend.agents.department.research import research_agent
    return {
        "sales_agent": sales_agent,
        "support_agent": support_agent,
        "research_agent": research_agent,
    }


async def executor_node(state: ABOSState) -> Dict[str, Any]:
    """
    LangGraph node: Step Executor.

    Picks the current step from workflow_plan[current_step_index],
    runs it via the assigned department agent, and updates the step status.

    Reads:  workflow_plan, current_step_index
    Writes: workflow_plan (updated step), completed_steps or failed indicators,
            current_step_index (incremented on success), logs
    """
    plan = state.get("workflow_plan") or []
    step_idx = state.get("current_step_index", 0)

    if step_idx >= len(plan):
        logger.warning("[Executor] current_step_index out of bounds — nothing to execute.")
        return {"logs": ["Executor: no step to run."]}

    current_step: WorkflowStepState = dict(plan[step_idx])
    agent_name = current_step["assigned_agent"]

    logger.info(
        f"[Executor] Running step {step_idx}: '{current_step['title']}' "
        f"via agent '{agent_name}'"
    )

    # Mark step as running
    current_step["status"] = "running"
    updated_plan = list(plan)
    updated_plan[step_idx] = current_step

    # Get agent instance
    registry = _get_agent_registry()
    agent = registry.get(agent_name)

    if agent is None:
        current_step["status"] = "failed"
        current_step["error_message"] = f"Unknown agent: '{agent_name}'"
        updated_plan[step_idx] = current_step
        return {
            "workflow_plan": updated_plan,
            "logs": [f"Executor: unknown agent '{agent_name}' for step {step_idx}."],
        }

    # Build context from previously completed steps
    context = {
        "completed_steps": [
            {"title": s["title"], "output": s.get("output_data")}
            for s in state.get("completed_steps", [])
        ]
    }

    # Execute
    result = await agent.execute(current_step, context)

    current_step["latency_ms"] = result.get("latency_ms")

    if result["success"]:
        current_step["status"] = "completed"
        current_step["output_data"] = {"output": result["output"]}
        updated_plan[step_idx] = current_step
        return {
            "workflow_plan": updated_plan,
            "completed_steps": [current_step],
            "current_step_index": step_idx + 1,
            "logs": [
                f"Executor: step {step_idx} ('{current_step['title']}') "
                f"completed in {current_step['latency_ms']:.0f}ms."
            ],
        }
    else:
        current_step["status"] = "failed"
        current_step["error_message"] = result.get("error", "Unknown error")
        updated_plan[step_idx] = current_step
        return {
            "workflow_plan": updated_plan,
            "logs": [
                f"Executor: step {step_idx} ('{current_step['title']}') "
                f"failed — {current_step['error_message']}"
            ],
        }


async def summarizer_node(state: ABOSState) -> Dict[str, Any]:
    """
    LangGraph node: Run Summarizer.

    Called after all steps have been processed.
    Generates a natural-language summary of the workflow run.

    Reads:  goal_description, completed_steps, failed_steps, workflow_plan
    Writes: final_status, summary, logs
    """
    completed = state.get("completed_steps") or []
    failed = state.get("failed_steps") or []
    plan = state.get("workflow_plan") or []

    total = len(plan)
    n_completed = len(completed)
    n_failed = len(failed)

    if n_failed == 0:
        final_status = "completed"
    elif n_completed == 0:
        final_status = "failed"
    else:
        final_status = "partially_completed"

    # Format steps for the summary prompt
    completed_str = "\n".join(
        f"- [{s['assigned_department']}] {s['title']}: "
        f"{str(s.get('output_data', {}).get('output', 'done'))[:200]}"
        for s in completed
    ) or "None"

    failed_str = "\n".join(
        f"- [{s['assigned_department']}] {s['title']}: {s.get('error_message', 'unknown error')}"
        for s in failed
    ) or "None"

    try:
        response = await acompletion(
            model=settings.ACTIVE_LLM,
            messages=[
                {"role": "system", "content": SUMMARIZER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": SUMMARIZER_USER_PROMPT.format(
                        goal_description=state["goal_description"],
                        completed_steps=completed_str,
                        failed_steps=failed_str,
                    ),
                },
            ],
            temperature=0.3,
            max_tokens=512,
        )
        summary = response.choices[0].message.content
    except Exception as e:
        logger.error(f"[Summarizer] LLM call failed: {e}")
        summary = (
            f"Workflow {'completed' if final_status == 'completed' else 'partially completed'}. "
            f"{n_completed}/{total} steps successful, {n_failed} failed."
        )

    logger.info(
        f"[Summarizer] goal_id={state['goal_id']}: "
        f"status={final_status}, {n_completed}/{total} completed."
    )

    return {
        "final_status": final_status,
        "summary": summary,
        "logs": [f"Summarizer: workflow {final_status}. {n_completed}/{total} steps completed."],
    }
