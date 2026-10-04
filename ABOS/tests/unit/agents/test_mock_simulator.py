"""
Unit tests for MockSimulator (controlled stochastic tool execution).
"""

from unittest.mock import patch
import pytest
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
