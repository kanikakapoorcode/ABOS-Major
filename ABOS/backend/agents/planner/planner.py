"""
Goal-to-Workflow Planner Node — Research Contribution #1

Takes a high-level business goal from ABOSState and produces a structured
list of WorkflowStepState objects by calling the LLM via LiteLLM.

This is the core novelty: translating business goals (not single-turn prompts)
into multi-department executable workflows.
"""

import json
import logging
from typing import Any, Dict, List

from litellm import acompletion
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.agents.state import ABOSState, WorkflowStepState
from backend.agents.planner.prompts import (
    PLANNER_SYSTEM_PROMPT,
    PLANNER_USER_PROMPT,
    MEMORY_SECTION_TEMPLATE,
    CONTEXT_SECTION_TEMPLATE,
    DEPARTMENT_HINT_TEMPLATE,
)
from backend.core.config import settings

logger = logging.getLogger(__name__)

VALID_DEPARTMENTS = {"sales", "support", "research"}
VALID_AGENTS = {"sales_agent", "support_agent", "research_agent"}


def _build_memory_section(retrieved_memory: List[Dict[str, Any]]) -> str:
    """Format retrieved feedback for injection into the planner prompt."""
    if not retrieved_memory:
        return ""
    items = []
    for i, mem in enumerate(retrieved_memory[:5], 1):
        line = f"  {i}. Rating: {mem.get('rating')} | Correction: {mem.get('correction', 'N/A')} | Suggested agent: {mem.get('suggested_agent', 'N/A')}"
        items.append(line)
    return MEMORY_SECTION_TEMPLATE.format(feedback_items="\n".join(items))


def _build_system_prompt(state: ABOSState) -> str:
    memory_section = _build_memory_section(state.get("retrieved_memory") or [])
    return PLANNER_SYSTEM_PROMPT.format(memory_section=memory_section)


def _build_user_prompt(state: ABOSState) -> str:
    context_section = ""
    if state.get("goal_context"):
        context_section = CONTEXT_SECTION_TEMPLATE.format(context=json.dumps(state["goal_context"]))

    dept_section = ""
    if state.get("target_departments"):
        dept_section = DEPARTMENT_HINT_TEMPLATE.format(
            departments=", ".join(state["target_departments"])
        )

    return PLANNER_USER_PROMPT.format(
        goal_title=state["goal_title"],
        goal_priority=state["goal_priority"],
        goal_description=state["goal_description"],
        context_section=context_section,
        department_hint_section=dept_section,
    )


def _parse_plan(raw: str) -> List[WorkflowStepState]:
    """
    Parse and validate the LLM JSON response into WorkflowStepState list.
    Raises ValueError if the output is malformed.
    """
    try:
        # Strip markdown code fences if the model includes them despite instructions
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        steps_raw = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Planner returned invalid JSON: {e}\nRaw output: {raw[:500]}")

    if not isinstance(steps_raw, list) or len(steps_raw) == 0:
        raise ValueError("Planner returned empty or non-list response.")

    steps: List[WorkflowStepState] = []
    for i, raw_step in enumerate(steps_raw):
        dept = raw_step.get("assigned_department", "").lower()
        agent = raw_step.get("assigned_agent", "").lower()

        if dept not in VALID_DEPARTMENTS:
            logger.warning(f"Step {i}: unknown department '{dept}', defaulting to 'research'")
            dept = "research"
            agent = "research_agent"

        if agent not in VALID_AGENTS:
            agent = f"{dept}_agent"

        step: WorkflowStepState = {
            "step_index": raw_step.get("step_index", i),
            "title": str(raw_step.get("title", f"Step {i}"))[:200],
            "description": str(raw_step.get("description", ""))[:1000],
            "assigned_department": dept,
            "assigned_agent": agent,
            "input_data": raw_step.get("input_data") or {},
            "output_data": None,
            "status": "pending",
            "retry_count": 0,
            "latency_ms": None,
            "scheduler_score": None,
            "error_message": None,
        }
        steps.append(step)

    return steps


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def _call_planner_llm(system_prompt: str, user_prompt: str) -> str:
    """Call the LLM via LiteLLM with retry on transient errors."""
    response = await acompletion(
        model=settings.ACTIVE_LLM,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=2048,
    )
    return response.choices[0].message.content


async def planner_node(state: ABOSState) -> Dict[str, Any]:
    """
    LangGraph node: Goal-to-Workflow Planner.

    Reads: goal_description, goal_title, goal_priority, goal_context,
           target_departments, retrieved_memory
    Writes: workflow_plan, logs
    """
    logger.info(f"[Planner] Starting for goal_id={state['goal_id']}")

    system_prompt = _build_system_prompt(state)
    user_prompt = _build_user_prompt(state)

    try:
        raw_output = await _call_planner_llm(system_prompt, user_prompt)
        plan = _parse_plan(raw_output)
        logger.info(f"[Planner] Generated {len(plan)} steps for goal_id={state['goal_id']}")
        return {
            "workflow_plan": plan,
            "current_step_index": 0,
            "logs": [f"Planner generated {len(plan)}-step workflow."],
        }
    except Exception as e:
        logger.error(f"[Planner] Failed for goal_id={state['goal_id']}: {e}")
        return {
            "workflow_plan": [],
            "final_status": "failed",
            "error": f"Planner failed: {str(e)}",
            "logs": [f"Planner error: {str(e)}"],
        }
