"""
Unit tests for the Goal-to-Workflow Planner.
"""

import pytest
from backend.agents.planner.planner import (
    _build_memory_section,
    _build_system_prompt,
    _build_user_prompt,
    _parse_plan,
)
from backend.agents.state import ABOSState


def test_build_memory_section():
    feedback = [
        {"rating": "negative", "correction": "Route lead search to sales", "suggested_agent": "sales_outreach_fast"},
        {"rating": "positive", "correction": "Great work on support", "suggested_agent": "support_tier1_fast"},
    ]
    section = _build_memory_section(feedback)
    assert "PAST FEEDBACK" in section
    assert "Route lead search to sales" in section
    assert "sales_outreach_fast" in section

    empty_section = _build_memory_section([])
    assert empty_section == ""


def test_build_prompts():
    state: ABOSState = {
        "goal_id": "test-1",
        "workflow_id": "wf-1",
        "user_id": "u-1",
        "goal_title": "Enterprise Outreach",
        "goal_description": "Find inactive accounts and reach out",
        "goal_priority": "high",
        "goal_context": {"industry": "tech"},
        "target_departments": ["sales"],
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

    sys_prompt = _build_system_prompt(state)
    assert "You are the Workflow Planner" in sys_prompt

    user_prompt = _build_user_prompt(state)
    assert "Enterprise Outreach" in user_prompt
    assert "Find inactive accounts and reach out" in user_prompt
    assert "tech" in user_prompt
    assert "sales" in user_prompt


def test_parse_plan_valid_json_list():
    raw = """
    [
        {
            "step_index": 0,
            "title": "Search cold enterprise leads",
            "description": "Find accounts with no touch in 90 days",
            "assigned_department": "sales",
            "assigned_agent": "sales_agent",
            "task_type": "lead_search",
            "input_data": {"threshold_days": 90}
        },
        {
            "step_index": 1,
            "title": "Analyze churn risk",
            "description": "Examine behavior metrics",
            "assigned_department": "research",
            "assigned_agent": "research_agent",
            "task_type": "churn_detection",
            "input_data": {}
        }
    ]
    """
    steps = _parse_plan(raw)
    assert len(steps) == 2
    assert steps[0]["assigned_department"] == "sales"
    assert steps[0]["task_type"] == "lead_search"
    assert steps[1]["assigned_department"] == "research"
    assert steps[1]["task_type"] == "churn_detection"


def test_parse_plan_markdown_fences():
    raw = """```json
    [
        {
            "step_index": 0,
            "title": "Draft response",
            "description": "Draft ticket reply",
            "assigned_department": "support",
            "assigned_agent": "support_agent",
            "task_type": "response_drafting",
            "input_data": {}
        }
    ]
    ```"""
    steps = _parse_plan(raw)
    assert len(steps) == 1
    assert steps[0]["assigned_department"] == "support"
    assert steps[0]["task_type"] == "response_drafting"


def test_parse_plan_dict_wrapper():
    raw = """{
        "steps": [
            {
                "step_index": 0,
                "title": "Generate report",
                "description": "Generate executive summary",
                "assigned_department": "research",
                "assigned_agent": "research_agent",
                "task_type": "report_generation",
                "input_data": {}
            }
        ]
    }"""
    steps = _parse_plan(raw)
    assert len(steps) == 1
    assert steps[0]["title"] == "Generate report"
    assert steps[0]["task_type"] == "report_generation"


def test_parse_plan_invalid_department_fallback():
    raw = """[
        {
            "step_index": 0,
            "title": "Unknown Department Step",
            "description": "Something strange",
            "assigned_department": "marketing",
            "assigned_agent": "marketing_agent",
            "task_type": "unknown_task",
            "input_data": {}
        }
    ]"""
    steps = _parse_plan(raw)
    assert len(steps) == 1
    # Fallback department is 'research'
    assert steps[0]["assigned_department"] == "research"
    assert steps[0]["assigned_agent"] == "research_agent"
    assert steps[0]["task_type"] is None


def test_parse_plan_malformed_json():
    with pytest.raises(ValueError, match="invalid JSON"):
        _parse_plan("This is not JSON at all")


def test_parse_plan_empty_list():
    with pytest.raises(ValueError, match="empty or non-list"):
        _parse_plan("[]")
