"""
Compliance Validation Module — ABOS

Two LangGraph nodes that act as compliance gatekeepers:

1. compliance_plan_node  — runs AFTER the planner, BEFORE the scheduler.
   Reviews the full proposed workflow plan for regulatory and legal risks.
   Blocks execution of "high" / "critical" risk plans; lets "low" / "medium" proceed with flags.

2. compliance_output_node — runs AFTER each executor step, BEFORE advancing to the next step.
   Reviews individual step outputs for compliance violations in the produced content.
   Injects a compliance_blocked failure if an output is unsafe to pass forward.

Both nodes use LiteLLM so they inherit the active LLM provider from settings.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from litellm import acompletion
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.agents.state import ABOSState, WorkflowStepState
from backend.agents.planner.prompts import (
    COMPLIANCE_PLAN_SYSTEM_PROMPT,
    COMPLIANCE_PLAN_USER_PROMPT,
    COMPLIANCE_OUTPUT_SYSTEM_PROMPT,
    COMPLIANCE_OUTPUT_USER_PROMPT,
)
from backend.core.config import settings

logger = logging.getLogger(__name__)


# ── Shared LLM helper ─────────────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    reraise=True,
)
async def _call_compliance_llm(system_prompt: str, user_prompt: str) -> str:
    """Single LLM call for compliance review. Returns raw text."""
    response = await acompletion(
        model=settings.ACTIVE_LLM,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,   # low temperature — we want deterministic risk assessment
        max_tokens=600,
    )
    return response.choices[0].message.content


def _parse_json_safe(raw: str, fallback: Dict) -> Dict:
    """Parse JSON from LLM output, stripping markdown fences. Returns fallback on failure."""
    try:
        cleaned = raw.strip()
        if "```" in cleaned:
            parts = cleaned.split("```")
            cleaned = parts[1] if len(parts) >= 3 else parts[-1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        return json.loads(cleaned.strip())
    except Exception as e:
        logger.warning(f"[Compliance] Failed to parse JSON: {e}. Raw: {raw[:300]}")
        return fallback


# ── Node 1: Plan-level compliance check ──────────────────────────────────────

async def compliance_plan_node(state: ABOSState) -> Dict[str, Any]:
    """
    LangGraph node: Plan Compliance Check.

    Runs after the planner and before the scheduler.
    Reviews the full workflow plan for regulatory/legal/factual risks.

    Reads:  workflow_plan, goal_description, goal_context
    Writes: compliance_plan_result, compliance_flags, logs
            If plan is blocked: final_status = "compliance_blocked", workflow_plan = []
    """
    plan = state.get("workflow_plan") or []
    goal_description = state.get("goal_description", "")
    goal_context = state.get("goal_context") or {}

    if not plan:
        return {"logs": ["Compliance plan check: no plan to review."]}

    logger.info(
        f"[Compliance] Reviewing plan with {len(plan)} steps "
        f"for goal_id={state.get('goal_id')}"
    )

    # Serialize plan for the LLM (strip internal runtime fields)
    plan_summary = [
        {
            "step_index": s["step_index"],
            "title": s["title"],
            "description": s["description"],
            "assigned_department": s["assigned_department"],
            "task_type": s.get("task_type"),
            "input_data": s.get("input_data", {}),
        }
        for s in plan
    ]

    user_prompt = COMPLIANCE_PLAN_USER_PROMPT.format(
        goal_description=goal_description,
        goal_context=json.dumps(goal_context, indent=2) if goal_context else "Not provided",
        workflow_plan_json=json.dumps(plan_summary, indent=2),
    )

    fallback_result = {
        "plan_approved": True,
        "overall_risk": "low",
        "step_findings": [],
        "blocking_issues": [],
        "advisory_notes": ["Compliance check skipped due to LLM error — proceed with caution."],
    }

    try:
        raw = await _call_compliance_llm(COMPLIANCE_PLAN_SYSTEM_PROMPT, user_prompt)
        result = _parse_json_safe(raw, fallback_result)
    except Exception as e:
        logger.error(f"[Compliance] Plan check LLM call failed: {e}. Allowing plan through.")
        result = fallback_result

    plan_approved = result.get("plan_approved", True)
    overall_risk = result.get("overall_risk", "low")
    blocking_issues = result.get("blocking_issues", [])
    advisory_notes = result.get("advisory_notes", [])

    # Collect all compliance flags (blocking + advisory) for summarizer
    flags: List[str] = []
    for issue in blocking_issues:
        flags.append(f"[BLOCKED] {issue}")
    for note in advisory_notes:
        flags.append(f"[ADVISORY] {note}")
    for finding in result.get("step_findings", []):
        if not finding.get("compliant", True):
            flags.append(
                f"[Step {finding['step_index']} — {finding.get('risk_level', 'unknown').upper()}] "
                f"{'; '.join(finding.get('issues', []))}"
            )

    log_lines = [
        f"Compliance plan check: approved={plan_approved}, "
        f"risk={overall_risk}, "
        f"blocking_issues={len(blocking_issues)}, "
        f"advisory_notes={len(advisory_notes)}."
    ]

    if not plan_approved:
        logger.warning(
            f"[Compliance] Plan BLOCKED for goal_id={state.get('goal_id')}. "
            f"Issues: {blocking_issues}"
        )
        return {
            "workflow_plan": [],           # clear plan to halt execution
            "final_status": "compliance_blocked",
            "compliance_plan_result": result,
            "compliance_flags": flags,
            "error": (
                "Workflow plan blocked by compliance review. "
                f"Issues: {'; '.join(blocking_issues)}"
            ),
            "logs": log_lines + [
                f"Compliance BLOCKED: {issue}" for issue in blocking_issues
            ],
        }

    logger.info(
        f"[Compliance] Plan approved (risk={overall_risk}) "
        f"for goal_id={state.get('goal_id')}."
    )
    return {
        "compliance_plan_result": result,
        "compliance_flags": flags,
        "logs": log_lines,
    }


# ── Node 2: Per-step output compliance check ─────────────────────────────────

async def compliance_output_node(state: ABOSState) -> Dict[str, Any]:
    """
    LangGraph node: Step Output Compliance Check.

    Runs after each executor step completes, before advancing to the next step.
    Reviews the step's output content for compliance violations.

    Reads:  workflow_plan, current_step_index (points to the JUST-COMPLETED step, i.e. index - 1)
    Writes: compliance_flags (appended), logs
            If output is unsafe: marks step as compliance_failed in workflow_plan
    """
    plan = state.get("workflow_plan") or []
    # current_step_index was already incremented by the executor on success
    # so the completed step is at index - 1
    completed_idx = state.get("current_step_index", 1) - 1

    if completed_idx < 0 or completed_idx >= len(plan):
        return {"logs": ["Compliance output check: index out of range, skipping."]}

    step: WorkflowStepState = dict(plan[completed_idx])

    # Only check completed steps
    if step.get("status") != "completed":
        return {"logs": [f"Compliance output check: step {completed_idx} not completed, skipping."]}

    output_data = step.get("output_data") or {}
    output_text = output_data.get("output", "")

    if not output_text:
        return {"logs": [f"Compliance output check: step {completed_idx} has no output, skipping."]}

    logger.info(
        f"[Compliance] Reviewing output of step {completed_idx}: '{step['title']}'"
    )

    user_prompt = COMPLIANCE_OUTPUT_USER_PROMPT.format(
        step_title=step["title"],
        department=step["assigned_department"],
        task_type=step.get("task_type") or "unspecified",
        step_description=step["description"],
        step_output=str(output_text)[:1500],   # cap to avoid token overflow
    )

    fallback_result = {
        "output_approved": True,
        "risk_level": "low",
        "issues": [],
        "recommendation": "",
        "safe_to_proceed": True,
    }

    try:
        raw = await _call_compliance_llm(COMPLIANCE_OUTPUT_SYSTEM_PROMPT, user_prompt)
        result = _parse_json_safe(raw, fallback_result)
    except Exception as e:
        logger.error(
            f"[Compliance] Output check LLM call failed for step {completed_idx}: {e}. "
            "Allowing output through."
        )
        result = fallback_result

    output_approved = result.get("output_approved", True)
    risk_level = result.get("risk_level", "low")
    issues = result.get("issues", [])
    safe_to_proceed = result.get("safe_to_proceed", True)

    # Append flags to existing compliance_flags list
    existing_flags: List[str] = list(state.get("compliance_flags") or [])
    new_flags: List[str] = []

    if not output_approved or risk_level in ("high", "critical"):
        flag_prefix = f"[Step {completed_idx} OUTPUT — {risk_level.upper()}]"
        for issue in issues:
            new_flags.append(f"{flag_prefix} {issue}")

    log_lines = [
        f"Compliance output check step {completed_idx} ('{step['title']}'): "
        f"approved={output_approved}, risk={risk_level}, "
        f"safe_to_proceed={safe_to_proceed}."
    ]

    if not safe_to_proceed:
        # Mark the step as compliance_failed so recovery/summarizer sees it
        updated_step = dict(step)
        updated_step["status"] = "compliance_failed"
        updated_step["error_message"] = (
            f"Output blocked by compliance review (risk={risk_level}). "
            f"Issues: {'; '.join(issues)}. "
            f"Recommendation: {result.get('recommendation', '')}"
        )
        updated_plan = list(plan)
        updated_plan[completed_idx] = updated_step

        logger.warning(
            f"[Compliance] Output BLOCKED for step {completed_idx}: {issues}"
        )
        return {
            "workflow_plan": updated_plan,
            "compliance_flags": existing_flags + new_flags,
            "logs": log_lines + [
                f"Compliance output BLOCKED step {completed_idx}: {issue}"
                for issue in issues
            ],
        }

    if new_flags:
        logger.info(
            f"[Compliance] Step {completed_idx} output approved with "
            f"{risk_level} risk advisory."
        )

    return {
        "compliance_flags": existing_flags + new_flags,
        "logs": log_lines,
    }
