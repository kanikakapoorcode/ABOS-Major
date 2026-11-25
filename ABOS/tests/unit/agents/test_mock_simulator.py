"""
Unit tests for MockSimulator (controlled stochastic tool execution).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.tools import tool

from backend.agents.department.base import BaseDepartmentAgent
from backend.agents.department.mock_simulator import (
    MockSimulator,
    ToolExecutionError,
    TOOL_PROFILES,
)


@pytest.fixture(autouse=True)
def no_sleep():
    with patch("asyncio.sleep", return_value=None):
        yield


@pytest.mark.asyncio
async def test_mock_simulator_deterministic_with_seed():
    sim1 = MockSimulator(seed=42)
    sim2 = MockSimulator(seed=42)

    data = {"sample": "data"}

    # Test identical execution results across runs with same seed
    try:
        res1 = await sim1.run("search_leads", data)
        failed1 = False
    except ToolExecutionError:
        failed1 = True

    try:
        res2 = await sim2.run("search_leads", data)
        failed2 = False
    except ToolExecutionError:
        failed2 = True

    assert failed1 == failed2
    if not failed1:
        assert res1 == res2


@pytest.mark.asyncio
async def test_mock_simulator_profiles_exist():
    assert "search_leads" in TOOL_PROFILES
    assert "triage_ticket" in TOOL_PROFILES
    assert "query_data" in TOOL_PROFILES

    sim = MockSimulator(seed=123)
    profile = sim._profile("search_leads")
    assert profile.failure_rate > 0
    assert profile.latency_mean_ms > 0


@pytest.mark.asyncio
async def test_mock_simulator_forces_failure_on_high_prob():
    # Test that error is raised and has expected tool_error prefix
    sim = MockSimulator(seed=1)
    found_error = False
    for _ in range(50):
        try:
            await sim.run("detect_churn_signals", {"res": "ok"})
        except ToolExecutionError as e:
            assert "tool_error" in str(e)
            found_error = True
            break

    assert found_error, "Should have encountered at least one simulated failure across 50 calls"


@pytest.mark.asyncio
async def test_department_agent_executes_only_registered_tool_calls():
    @tool
    def check_stock(current_stock: int, minimum_stock: int) -> str:
        """Check whether current stock is below the minimum."""
        return "below minimum" if current_stock <= minimum_stock else "sufficient"

    class StockAgent(BaseDepartmentAgent):
        name = "stock_agent"
        department = "research"

        def _get_system_prompt(self) -> str:
            return "Check stock and report the result."

    agent = StockAgent()
    agent.tools = [check_stock]
    tool_call = SimpleNamespace(
        id="call-1",
        function=SimpleNamespace(
            name="check_stock",
            arguments='{"current_stock": 2, "minimum_stock": 5}',
        ),
    )
    tool_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=None, tool_calls=[tool_call])
            )
        ]
    )
    final_response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="This product is below minimum.", tool_calls=None)
            )
        ]
    )

    with patch(
        "backend.agents.department.base.acompletion",
        new=AsyncMock(side_effect=[tool_response, final_response]),
    ) as completion:
        result = await agent.execute(
            {
                "step_index": 0,
                "title": "Review stock",
                "description": "Check the product's stock level.",
                "assigned_department": "research",
                "assigned_agent": "stock_agent",
                "task_type": "inventory_review",
                "input_data": {"current_stock": 2, "minimum_stock": 5},
                "output_data": None,
                "status": "pending",
                "retry_count": 0,
                "latency_ms": None,
                "scheduler_score": None,
                "error_message": None,
            },
            {},
        )

    assert result["success"] is True
    assert result["output"] == "This product is below minimum."
    assert completion.await_count == 2
    tool_messages = [
        message
        for message in completion.await_args_list[1].kwargs["messages"]
        if message["role"] == "tool"
    ]
    assert tool_messages == [
        {
            "role": "tool",
            "tool_call_id": "call-1",
            "name": "check_stock",
            "content": '"below minimum"',
        }
    ]
