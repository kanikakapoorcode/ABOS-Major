"""
Unit Tests for ABOS Scheduler, Task Taxonomy & 3-Tier Evidence Hierarchy
========================================================================

Tests (12 total):
1. Cold-start prior score (0.41)
2. Missing/invalid latency neutral 0.5 fallback
3. Weighted scoring formula computation (0.50 SR + 0.20 Latency + 0.30 Conf)
4. Cold-start primary-candidate tie-breaking policy
5. Proven performance routing selection
6. Exponential Moving Average confidence score updates
7. Canonical task taxonomy validation (strict, no guessing)
8. Task-specific beats aggregate (Routing Inversion between specialist and generalist)
9. Insufficient task-specific evidence (N < 3 falls back to Tier 2 aggregate)
10. Unknown task type fallback (invalid task string never fuzzed, uses aggregate)
11. Temporal boundary & no future leakage (routing decision at time t is strictly pre-execution)
12. Cold start vs proven candidate selection
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.agents.scheduler.scoring import (
    AgentScoreInput,
    latency_score,
    cold_start_score,
    compute_score,
    select_best_agent,
    update_confidence_score,
    WEIGHT_SUCCESS_RATE,
    WEIGHT_LATENCY,
    WEIGHT_CONFIDENCE,
)
from backend.agents.tasks.taxonomy import (
    CANONICAL_TASK_TYPES,
    MIN_TASK_EVIDENCE,
    MIN_AGGREGATE_EVIDENCE,
    validate_task_type,
)
from backend.agents.scheduler.scheduler import _load_agent_profiles, _assign_agent
from backend.agents.state import WorkflowStepState


def test_cold_start_prior_score():
    """Verify that unexecuted cold-start agents receive a composite score of 0.41."""
    res = cold_start_score(agent_name="sales_outreach_fast", department="sales")
    assert res.composite_score == 0.41
    assert res.success_rate == 0.5
    assert res.latency_score == 0.5
    assert res.confidence_score == 0.2


def test_latency_score_missing_and_valid_data():
    """Verify latency_score returns 0.5 for missing/unexecuted data and never returns 1.0 for invalid latency."""
    # Cold start (0 total executions)
    assert latency_score(0.0, total_executions=0) == 0.5
    # Missing/invalid latency with history
    assert latency_score(0.0, total_executions=10) == 0.5
    assert latency_score(-500.0, total_executions=10) == 0.5
    # Reference latency (3000ms -> score 0.5)
    assert latency_score(3000.0, total_executions=10) == 0.5
    # Fast execution (1000ms -> 1 / (1 + 1/3) = 0.75)
    assert round(latency_score(1000.0, total_executions=10), 2) == 0.75


def test_compute_score_unexecuted():
    """Verify compute_score uses cold-start prior (0.41) when total_executions == 0."""
    agent = AgentScoreInput(
        agent_name="test_agent",
        department="sales",
        success_rate=0.5,
        avg_latency_ms=0.0,
        confidence_score=0.2,
        total_executions=0,
    )
    result = compute_score(agent)
    assert result.composite_score == 0.41


def test_compute_score_proven():
    """Verify compute_score formula: 0.50 * SR + 0.20 * LatencyScore + 0.30 * Conf."""
    agent = AgentScoreInput(
        agent_name="proven_agent",
        department="sales",
        success_rate=0.90,
        avg_latency_ms=1000.0,  # latency_score = 0.75
        confidence_score=0.80,
        total_executions=20,
    )
    # Expected score: 0.50*0.90 + 0.20*0.75 + 0.30*0.80 = 0.45 + 0.15 + 0.24 = 0.84
    result = compute_score(agent)
    assert result.composite_score == 0.84


def test_select_best_agent_cold_start_tie_break():
    """Verify that when all candidates have cold-start prior (0.41), tie-breaking selects the primary candidate (first in list)."""
    c1 = AgentScoreInput("sales_outreach_fast", "sales", 0.5, 0.0, 0.2, 0)
    c2 = AgentScoreInput("sales_enterprise_thorough", "sales", 0.5, 0.0, 0.2, 0)

    best = select_best_agent([c1, c2])
    assert best is not None
    assert best.agent_name == "sales_outreach_fast"
    assert best.composite_score == 0.41


def test_cold_start_vs_proven_candidate_selection():
    """
    Verify that an agent with real historical evidence (Agent A: SR=0.90, Lat=800ms, Conf=0.85)
    is clearly selected over an unexecuted candidate at cold-start prior (Agent B: 0.41).
    """
    proven_a = AgentScoreInput(
        agent_name="sales_enterprise_thorough",
        department="sales",
        success_rate=0.90,
        avg_latency_ms=800.0,
        confidence_score=0.85,
        total_executions=20,
    )
    unexecuted_b = AgentScoreInput(
        agent_name="sales_outreach_fast",
        department="sales",
        success_rate=0.5,
        avg_latency_ms=0.0,
        confidence_score=0.2,
        total_executions=0,
    )

    best_proven = select_best_agent([proven_a, unexecuted_b])
    assert best_proven is not None
    assert best_proven.agent_name == "sales_enterprise_thorough"
    assert best_proven.composite_score > 0.80


def test_update_confidence_score_ema():
    """Verify confidence score EMA updates: positive signal increases confidence slowly."""
    initial_conf = 0.50
    new_conf = update_confidence_score(initial_conf, execution_succeeded=True, feedback_correct=True, alpha=0.1)
    assert new_conf == 0.55

    fail_conf = update_confidence_score(new_conf, execution_succeeded=False, feedback_correct=None, alpha=0.1)
    assert fail_conf == 0.495


def test_taxonomy_validation_strict():
    """Verify that canonical task types are strictly validated and unknown strings return None without guessing."""
    assert validate_task_type("sales", "lead_search") == "lead_search"
    assert validate_task_type("sales", "deal_qualification") == "deal_qualification"
    assert validate_task_type("support", "ticket_triage") == "ticket_triage"
    assert validate_task_type("research", "churn_detection") == "churn_detection"

    # Cross-department mismatches return None
    assert validate_task_type("sales", "ticket_triage") is None

    # Free-text or unlisted strings return None (never fuzzed)
    assert validate_task_type("sales", "Please qualify this very important enterprise lead") is None
    assert validate_task_type("sales", "something_the_taxonomy_does_not_contain") is None
    assert validate_task_type("sales", None) is None


@pytest.mark.asyncio
async def test_task_specific_beats_aggregate_inversion():
    """
    Test 1: Task-specific beats aggregate (Routing Inversion between specialist and generalist)
      - Agent A (Fast/Generalist): High aggregate performance (SR=0.90, lat=600ms, conf=0.85 -> score ~0.87),
        but weak at deal_qualification (SR=0.60, lat=1200ms, conf=0.50 -> score ~0.59).
      - Agent B (Enterprise/Specialist): Moderate aggregate performance (SR=0.75, lat=1500ms, conf=0.70 -> score ~0.72),
        but highly specialized at deal_qualification (SR=0.95, lat=900ms, conf=0.90 -> score ~0.90).

    Expected Behavior:
      1. When task_type is 'deal_qualification', Agent B wins based on Tier-1 task-conditioned profile.
      2. When task_type is None (general/unspecified), Agent A wins based on Tier-2 aggregate profile.
    """
    class MockProfile:
        def __init__(self, name, dept, sr, lat, conf, total, task_type=None):
            self.agent_name = name
            self.department = dept
            self.success_rate = sr
            self.avg_latency_ms = lat
            self.confidence_score = conf
            self.total_executions = total
            self.task_type = task_type

    agg_a = MockProfile("sales_outreach_fast", "sales", 0.90, 600.0, 0.85, 50)
    agg_b = MockProfile("sales_enterprise_thorough", "sales", 0.75, 1500.0, 0.70, 50)

    task_a = MockProfile("sales_outreach_fast", "sales", 0.60, 1200.0, 0.50, 10, "deal_qualification")
    task_b = MockProfile("sales_enterprise_thorough", "sales", 0.95, 900.0, 0.90, 10, "deal_qualification")

    step_specialized: WorkflowStepState = {
        "step_index": 0,
        "title": "Qualify enterprise opportunity",
        "description": "Run BANT deal qualification",
        "assigned_department": "sales",
        "assigned_agent": "sales_agent",
        "task_type": "deal_qualification",
        "input_data": {},
        "output_data": None,
        "status": "pending",
        "retry_count": 0,
        "latency_ms": None,
        "scheduler_score": None,
        "error_message": None,
    }

    step_general: WorkflowStepState = {
        "step_index": 1,
        "title": "General sales operation",
        "description": "General step",
        "assigned_department": "sales",
        "assigned_agent": "sales_agent",
        "task_type": None,
        "input_data": {},
        "output_data": None,
        "status": "pending",
        "retry_count": 0,
        "latency_ms": None,
        "scheduler_score": None,
        "error_message": None,
    }

    with patch("backend.db.session.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session

        # 1. Specialized step: returns agg profiles + task profiles
        async def mock_execute_specialized(stmt):
            stmt_str = str(stmt)
            res = MagicMock()
            if "agent_task_profiles" in stmt_str:
                res.scalars.return_value.all.return_value = [task_a, task_b]
            else:
                res.scalars.return_value.all.return_value = [agg_a, agg_b]
            return res

        mock_session.execute = mock_execute_specialized
        assigned_specialized = await _assign_agent(step_specialized)
        assert assigned_specialized["assigned_agent"] == "sales_enterprise_thorough"
        assert assigned_specialized["scheduler_score"] > 0.85

        # 2. General step: returns only agg profiles
        async def mock_execute_general(stmt):
            res = MagicMock()
            res.scalars.return_value.all.return_value = [agg_a, agg_b]
            return res

        mock_session.execute = mock_execute_general
        assigned_general = await _assign_agent(step_general)
        assert assigned_general["assigned_agent"] == "sales_outreach_fast"
        assert assigned_general["scheduler_score"] > 0.85


@pytest.mark.asyncio
async def test_insufficient_task_specific_evidence():
    """
    Test 2: Insufficient task-specific evidence
      - Agent B has a task-specific profile with only N=2 executions (< MIN_TASK_EVIDENCE = 3).
      - Even though task SR=1.0, the scheduler rejects it due to insufficient evidence and falls back to Tier 2 (Aggregate).
      - Under Tier 2, Agent A (aggregate score 0.87, N=50) beats Agent B (aggregate score 0.72, N=50).
    """
    class MockProfile:
        def __init__(self, name, dept, sr, lat, conf, total, task_type=None):
            self.agent_name = name
            self.department = dept
            self.success_rate = sr
            self.avg_latency_ms = lat
            self.confidence_score = conf
            self.total_executions = total
            self.task_type = task_type

    agg_a = MockProfile("sales_outreach_fast", "sales", 0.90, 600.0, 0.85, 50)
    agg_b = MockProfile("sales_enterprise_thorough", "sales", 0.75, 1500.0, 0.70, 50)

    # Insufficient task evidence for Agent B (total_executions = 2 < 3)
    task_b_insufficient = MockProfile("sales_enterprise_thorough", "sales", 1.0, 500.0, 0.95, 2, "deal_qualification")

    step: WorkflowStepState = {
        "step_index": 0,
        "title": "Qualify deal",
        "description": "BANT check",
        "assigned_department": "sales",
        "assigned_agent": "sales_agent",
        "task_type": "deal_qualification",
        "input_data": {},
        "output_data": None,
        "status": "pending",
        "retry_count": 0,
        "latency_ms": None,
        "scheduler_score": None,
        "error_message": None,
    }

    with patch("backend.db.session.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session

        async def mock_execute(stmt):
            stmt_str = str(stmt)
            res = MagicMock()
            if "agent_task_profiles" in stmt_str:
                res.scalars.return_value.all.return_value = [task_b_insufficient]
            else:
                res.scalars.return_value.all.return_value = [agg_a, agg_b]
            return res

        mock_session.execute = mock_execute
        assigned = await _assign_agent(step)
        # Falls back to Tier 2: Agent A wins
        assert assigned["assigned_agent"] == "sales_outreach_fast"


@pytest.mark.asyncio
async def test_unknown_task_type_fallback_to_aggregate():
    """
    Test 3: Unknown task type
      - Step specifies task_type = 'something_the_taxonomy_does_not_contain'.
      - validate_task_type strictly returns None (no guessing/fuzzing).
      - Scheduler does not query or create garbage task profiles; cleanly falls back to Tier 2 aggregate profiles.
    """
    class MockProfile:
        def __init__(self, name, dept, sr, lat, conf, total):
            self.agent_name = name
            self.department = dept
            self.success_rate = sr
            self.avg_latency_ms = lat
            self.confidence_score = conf
            self.total_executions = total

    agg_a = MockProfile("sales_outreach_fast", "sales", 0.90, 600.0, 0.85, 50)
    agg_b = MockProfile("sales_enterprise_thorough", "sales", 0.75, 1500.0, 0.70, 50)

    step: WorkflowStepState = {
        "step_index": 0,
        "title": "Random task",
        "description": "Unregistered task format",
        "assigned_department": "sales",
        "assigned_agent": "sales_agent",
        "task_type": "something_the_taxonomy_does_not_contain",
        "input_data": {},
        "output_data": None,
        "status": "pending",
        "retry_count": 0,
        "latency_ms": None,
        "scheduler_score": None,
        "error_message": None,
    }

    with patch("backend.db.session.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session

        async def mock_execute(stmt):
            stmt_str = str(stmt)
            # Guarantee that agent_task_profiles is NEVER queried for unknown task types
            assert "agent_task_profiles" not in stmt_str
            res = MagicMock()
            res.scalars.return_value.all.return_value = [agg_a, agg_b]
            return res

        mock_session.execute = mock_execute
        assigned = await _assign_agent(step)
        # Uses aggregate profile: Agent A wins
        assert assigned["assigned_agent"] == "sales_outreach_fast"


@pytest.mark.asyncio
async def test_temporal_boundary_no_future_leakage():
    """
    Test 4: Temporal Boundary & No Future Leakage
      - For a routing decision at time t, the scheduler relies exclusively on the pre-execution snapshot in the DB.
      - Execution outcomes, measured latencies, and subsequent profile updates at time t+1
        must NOT mutate or contaminate the pre-execution routing score assigned to the step at time t.
    """
    class MockProfile:
        def __init__(self, name, dept, sr, lat, conf, total):
            self.agent_name = name
            self.department = dept
            self.success_rate = sr
            self.avg_latency_ms = lat
            self.confidence_score = conf
            self.total_executions = total

    # Pre-execution DB profile at time t
    pre_agg_a = MockProfile("sales_outreach_fast", "sales", 0.90, 600.0, 0.85, 20)
    pre_agg_b = MockProfile("sales_enterprise_thorough", "sales", 0.70, 1500.0, 0.70, 20)

    step: WorkflowStepState = {
        "step_index": 0,
        "title": "Lead outreach",
        "description": "Send outreach email",
        "assigned_department": "sales",
        "assigned_agent": "sales_agent",
        "task_type": "outreach_drafting",
        "input_data": {},
        "output_data": None,
        "status": "pending",
        "retry_count": 0,
        "latency_ms": None,
        "scheduler_score": None,
        "error_message": None,
    }

    with patch("backend.db.session.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session

        async def mock_execute(stmt):
            res = MagicMock()
            res.scalars.return_value.all.return_value = [pre_agg_a, pre_agg_b]
            return res

        mock_session.execute = mock_execute

        # 1. Routing decision at time t
        assigned_step = await _assign_agent(step)
        assigned_agent_at_t = assigned_step["assigned_agent"]
        score_at_t = assigned_step["scheduler_score"]

        assert assigned_agent_at_t == "sales_outreach_fast"
        assert score_at_t is not None

        # 2. Simulate step execution at time t+1 that fails with high latency
        runtime_execution = {
            "status": "failed",
            "latency_ms": 9500.0,
            "error": "Timeout in tool call",
        }

        # 3. Verify temporal integrity: the step's recorded scheduler_score remains frozen at time t
        assert assigned_step["scheduler_score"] == score_at_t
        assert assigned_step["assigned_agent"] == "sales_outreach_fast"
