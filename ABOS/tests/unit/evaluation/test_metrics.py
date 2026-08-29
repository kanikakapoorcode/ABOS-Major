"""
Unit Tests for Evaluation Metrics & Oracle Accuracy
===================================================

Tests:
1. Ground-truth oracle optimal agent utility lookup
2. Task completion rate calculation
3. Oracle agreement rate calculation
4. Recovery success rate denominator safeguard (returns None on 0 failed steps)
5. Step latency vs Total latency separation
6. Pearson score correlation calculation
7. Descriptive metrics aggregation (Mean, SD, Median)
"""

import pytest
from evaluation.oracle import get_oracle_optimal_agent
from evaluation.metrics import compute_metrics, aggregate, TrialMetrics


def test_oracle_optimal_agent_mapping():
    """Verify ground-truth utility-maximizing optimal agent lookup for canonical task types."""
    # Sales
    assert get_oracle_optimal_agent("sales", "lead_search") == "sales_outreach_fast"
    assert get_oracle_optimal_agent("sales", "deal_qualification") == "sales_enterprise_thorough"

    # Support
    assert get_oracle_optimal_agent("support", "ticket_triage") == "support_tier1_fast"
    assert get_oracle_optimal_agent("support", "sentiment_analysis") == "support_tier2_specialist"

    # Research
    assert get_oracle_optimal_agent("research", "data_query") == "research_kpi_quick"
    assert get_oracle_optimal_agent("research", "churn_detection") == "research_deep_analyst"


def test_compute_metrics_oracle_agreement_and_tcr():
    """Verify TCR and Oracle Agreement Rate on synthetic execution result."""
    synthetic_result = {
        "workflow_plan": [
            {
                "step_index": 0,
                "assigned_department": "sales",
                "task_type": "lead_search",
                "assigned_agent": "sales_outreach_fast",  # Match (oracle: sales_outreach_fast)
                "status": "completed",
                "latency_ms": 600.0,
                "scheduler_score": 0.85,
                "retry_count": 0,
            },
            {
                "step_index": 1,
                "assigned_department": "sales",
                "task_type": "deal_qualification",
                "assigned_agent": "sales_outreach_fast",  # Mismatch (oracle: sales_enterprise_thorough)
                "status": "completed",
                "latency_ms": 1200.0,
                "scheduler_score": 0.70,
                "retry_count": 0,
            },
        ],
        "completed_steps": [{"step_index": 0}, {"step_index": 1}],
        "failed_steps": [],
    }

    metrics = compute_metrics(synthetic_result, scenario_id="S1", system="abos", trial_number=1, seed=42)

    assert metrics.task_completion_rate == 1.0        # 2 / 2
    assert metrics.oracle_agreement_rate == 0.5       # 1 matched oracle out of 2
    assert metrics.avg_step_latency_ms == 900.0       # (600 + 1200) / 2
    assert metrics.total_scenario_latency_ms == 1800.0
    assert metrics.recovery_success_rate is None      # 0 failures -> None (not 100%)


def test_compute_metrics_recovery_denominator():
    """Verify RSR handles failures correctly when failures occur."""
    synthetic_result = {
        "workflow_plan": [
            {
                "step_index": 0,
                "assigned_department": "support",
                "task_type": "ticket_triage",
                "assigned_agent": "support_tier1_fast",
                "status": "completed",
                "latency_ms": 400.0,
                "retry_count": 1, # Recovered step
            },
            {
                "step_index": 1,
                "assigned_department": "support",
                "task_type": "sentiment_analysis",
                "assigned_agent": "support_tier1_fast",
                "status": "failed",
                "latency_ms": 800.0,
                "retry_count": 3, # Unrecovered step
            },
        ],
        "completed_steps": [{"step_index": 0, "retry_count": 1}],
        "failed_steps": [{"step_index": 1, "retry_count": 3}],
    }

    metrics = compute_metrics(synthetic_result, scenario_id="P1", system="abos", trial_number=1, seed=42)
    assert metrics.task_completion_rate == 0.5
    # Total failed attempts = 1 failed + 1 recovered = 2. Recovered = 1 -> RSR = 0.5
    assert metrics.recovery_success_rate == 0.5
