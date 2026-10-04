"""
Unit tests for the Failure Classifier and Recovery Node.
"""

import pytest
from backend.agents.recovery.classifier import (
    classify_failure,
    decide_recovery_action,
    FailureType,
    RecoveryAction,
)
from backend.agents.recovery.recovery import recovery_node
from backend.agents.state import ABOSState, WorkflowStepState


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
