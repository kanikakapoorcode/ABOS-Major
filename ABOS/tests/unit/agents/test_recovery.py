"""
Unit tests for the Failure Classifier and Recovery Node.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.compliance.compliance import compliance_output_node
from backend.agents.executor import summarizer_node
from backend.agents.graph import route_after_compliance_output, route_after_executor
from backend.agents.recovery.classifier import (
    classify_failure,
    decide_recovery_action,
    FailureType,
    RecoveryAction,
)
from backend.agents.recovery.recovery import recovery_node
from backend.agents.state import ABOSState, WorkflowStepState


def test_executor_failure_after_completed_step_routes_to_recovery():
    state = {
        "workflow_plan": [
            {"step_index": 0, "status": "completed"},
            {"step_index": 1, "status": "failed"},
        ],
        "current_step_index": 1,
    }

    assert route_after_executor(state) == "recovery"


@pytest.mark.asyncio
async def test_blocked_output_stops_following_steps_and_is_reported_as_failed():
    completed_step = {
        "step_index": 0,
        "title": "Create outreach draft",
        "description": "Draft the message",
        "assigned_department": "sales",
        "assigned_agent": "sales_outreach_fast",
        "task_type": "outreach_drafting",
        "input_data": {},
        "output_data": {"output": "Unsafe content"},
        "status": "completed",
        "retry_count": 0,
        "latency_ms": 100.0,
        "scheduler_score": 0.8,
        "error_message": None,
    }
    next_step = {
        **completed_step,
        "step_index": 1,
        "title": "Send outreach",
        "status": "pending",
    }
    state = {
        "workflow_plan": [completed_step, next_step],
        "current_step_index": 1,
        "compliance_flags": [],
    }
    blocked_result = (
        '{"output_approved": false, "risk_level": "high", "issues": ["unsafe content"], '
        '"recommendation": "manual review", "safe_to_proceed": false}'
    )

    with patch(
        "backend.agents.compliance.compliance._call_compliance_llm",
        new=AsyncMock(return_value=blocked_result),
    ):
        result = await compliance_output_node(state)

    blocked_state = {**state, **result}
    assert blocked_state["workflow_plan"][0]["status"] == "compliance_failed"
    assert blocked_state["failed_steps"] == [blocked_state["workflow_plan"][0]]
    assert route_after_compliance_output(blocked_state) == "summarizer"

    response = MagicMock()
    response.choices[0].message.content = "The workflow was stopped."
    with (
        patch("backend.agents.executor.acompletion", new=AsyncMock(return_value=response)),
        patch(
            "backend.agents.executor.translate_output",
            new=AsyncMock(
                return_value={
                    "localised_summary": "The workflow was stopped.",
                    "localised_compliance_flags": [],
                }
            ),
        ),
    ):
        summary_result = await summarizer_node(
            {
                **blocked_state,
                "goal_id": "goal-1",
                "goal_description": "Create and send outreach",
                "completed_steps": [completed_step],
                "detected_language": "en",
                "logs": [],
            }
        )

    assert summary_result["final_status"] == "failed"
    assert "0/2 steps completed" in summary_result["logs"][0]


def test_classify_failure_rules():
    assert classify_failure("Connection timed out after 30s", 0, 3) == FailureType.TIMEOUT
    assert classify_failure("Rate limit reached (429)", 0, 3) == FailureType.LLM_ERROR
    assert classify_failure("tool_error: search_leads failed", 0, 3) == FailureType.TOOL_ERROR
    assert classify_failure("JSONDecodeError: invalid json", 0, 3) == FailureType.INVALID_OUTPUT
    assert classify_failure("Generic error", 2, 3) == FailureType.REROUTE
    assert classify_failure("Any error", 3, 3) == FailureType.UNRECOVERABLE


def test_decide_recovery_action():
    # Timeout
    assert decide_recovery_action(FailureType.TIMEOUT, 0, 3) == RecoveryAction.RETRY_WITH_TIMEOUT

    # Reroute with and without alternatives
    assert decide_recovery_action(FailureType.REROUTE, 2, 3, has_alternative_agent=True) == RecoveryAction.REROUTE
    assert decide_recovery_action(FailureType.REROUTE, 2, 3, has_alternative_agent=False) == RecoveryAction.SKIP

    # Transient error under limit
    assert decide_recovery_action(FailureType.TOOL_ERROR, 1, 3) == RecoveryAction.RETRY
    # Transient error at limit
    assert decide_recovery_action(FailureType.TOOL_ERROR, 3, 3) == RecoveryAction.SKIP

    # Unrecoverable
    assert decide_recovery_action(FailureType.UNRECOVERABLE, 3, 3) == RecoveryAction.SKIP


@pytest.mark.asyncio
async def test_recovery_node_retry():
    step: WorkflowStepState = {
        "step_index": 0,
        "title": "Lead Search",
        "description": "Search leads",
        "assigned_department": "sales",
        "assigned_agent": "sales_outreach_fast",
        "task_type": "lead_search",
        "input_data": {},
        "output_data": None,
        "status": "failed",
        "retry_count": 0,
        "latency_ms": 100.0,
        "scheduler_score": 0.8,
        "error_message": "tool_error: connection drop",
    }
    state: ABOSState = {
        "goal_id": "g-1",
        "workflow_id": "w-1",
        "user_id": "u-1",
        "goal_title": "Test Goal",
        "goal_description": "Test",
        "goal_priority": "high",
        "goal_context": None,
        "target_departments": ["sales"],
        "workflow_plan": [step],
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

    result = await recovery_node(state)
    updated_plan = result["workflow_plan"]
    assert updated_plan[0]["status"] == "retrying"
    assert updated_plan[0]["retry_count"] == 1
    assert result["recovery_attempts"] == 1


@pytest.mark.asyncio
async def test_recovery_node_reroute():
    step: WorkflowStepState = {
        "step_index": 0,
        "title": "Lead Search",
        "description": "Search leads",
        "assigned_department": "sales",
        "assigned_agent": "sales_outreach_fast",
        "task_type": "lead_search",
        "input_data": {},
        "output_data": None,
        "status": "failed",
        "retry_count": 2,
        "latency_ms": 100.0,
        "scheduler_score": 0.8,
        "error_message": "Agent consistently failing",
    }
    state: ABOSState = {
        "goal_id": "g-1",
        "workflow_id": "w-1",
        "user_id": "u-1",
        "goal_title": "Test Goal",
        "goal_description": "Test",
        "goal_priority": "high",
        "goal_context": None,
        "target_departments": ["sales"],
        "workflow_plan": [step],
        "current_step_index": 0,
        "completed_steps": [],
        "failed_steps": [],
        "retrieved_memory": [],
        "recovery_attempts": 2,
        "max_recovery_attempts": 3,
        "final_status": None,
        "summary": None,
        "error": None,
        "logs": [],
    }

    result = await recovery_node(state)
    updated_plan = result["workflow_plan"]
    assert updated_plan[0]["status"] == "retrying"
    assert updated_plan[0]["assigned_agent"] == "sales_enterprise_thorough"
    assert updated_plan[0]["retry_count"] == 3


@pytest.mark.asyncio
async def test_recovery_node_skip():
    step: WorkflowStepState = {
        "step_index": 0,
        "title": "Lead Search",
        "description": "Search leads",
        "assigned_department": "sales",
        "assigned_agent": "sales_enterprise_thorough",
        "task_type": "lead_search",
        "input_data": {},
        "output_data": None,
        "status": "failed",
        "retry_count": 3,
        "latency_ms": 100.0,
        "scheduler_score": 0.8,
        "error_message": "Unrecoverable error",
    }
    state: ABOSState = {
        "goal_id": "g-1",
        "workflow_id": "w-1",
        "user_id": "u-1",
        "goal_title": "Test Goal",
        "goal_description": "Test",
        "goal_priority": "high",
        "goal_context": None,
        "target_departments": ["sales"],
        "workflow_plan": [step],
        "current_step_index": 0,
        "completed_steps": [],
        "failed_steps": [],
        "retrieved_memory": [],
        "recovery_attempts": 3,
        "max_recovery_attempts": 3,
        "final_status": None,
        "summary": None,
        "error": None,
        "logs": [],
    }

    result = await recovery_node(state)
    updated_plan = result["workflow_plan"]
    assert updated_plan[0]["status"] == "failed"
    assert result["current_step_index"] == 1
    assert len(result["failed_steps"]) == 1


@pytest.mark.asyncio
async def test_compliance_output_does_not_duplicate_existing_flags():
    step = {
        "step_index": 1,
        "title": "Draft response",
        "description": "Draft customer response",
        "assigned_department": "support",
        "assigned_agent": "support_tier1_fast",
        "task_type": "response_drafting",
        "input_data": {},
        "output_data": {"output": "Draft body"},
        "status": "completed",
        "retry_count": 0,
        "latency_ms": 50.0,
        "scheduler_score": 0.8,
        "error_message": None,
    }
    state = {
        "workflow_plan": [step, step],
        "current_step_index": 2,
        "compliance_flags": ["[ADVISORY] Prior flag"],
    }
    advisory_json = (
        '{"output_approved": false, "risk_level": "high", "issues": ["New issue"], '
        '"recommendation": "Fix it", "safe_to_proceed": false}'
    )
    with patch(
        "backend.agents.compliance.compliance._call_compliance_llm",
        new=AsyncMock(return_value=advisory_json),
    ):
        result = await compliance_output_node(state)

    assert len(result["compliance_flags"]) == 1
    assert "[ADVISORY] Prior flag" not in result["compliance_flags"]
    assert "New issue" in result["compliance_flags"][0]


@pytest.mark.asyncio
async def test_summarizer_empty_plan_reports_failed():
    response = MagicMock()
    response.choices[0].message.content = "No steps ran."
    with (
        patch("backend.agents.executor.acompletion", new=AsyncMock(return_value=response)),
        patch(
            "backend.agents.executor.translate_output",
            new=AsyncMock(
                return_value={
                    "localised_summary": "No steps ran.",
                    "localised_compliance_flags": [],
                }
            ),
        ),
    ):
        res = await summarizer_node(
            {
                "goal_id": "g-empty",
                "goal_description": "Test empty plan",
                "workflow_plan": [],
                "completed_steps": [],
                "failed_steps": [],
                "compliance_flags": [],
                "detected_language": "en",
                "logs": [],
            }
        )
    assert res["final_status"] == "failed"
