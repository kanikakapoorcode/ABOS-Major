"""
Ground-Truth Oracle & Utility-Aligned Reference for Evaluation.

Defines the theoretically optimal candidate agent for each canonical task type
based on underlying tool execution feasibility and the mathematical evaluation
utility function:
    Utility(agent, task) = 0.50 * Sim_SR + 0.20 * LatencyScore(Sim_Latency) + 0.30 * Theoretical_Conf

IMPORTANT SCIENTIFIC CONSTRAINTS:
1. The parameters below are simulator-generating parameters / oracle reference values
   derived from the MockSimulator specification (SOURCE_OF_TRUTH.md §5), NOT historical
   database observations.
2. The runtime ABOS scheduler has ZERO access to this module or its underlying values;
   agreement is evaluated strictly post-hoc as `oracle_agreement_rate`.
"""

from typing import Dict, Tuple

# Simulator-generating parameters for tool execution per candidate
# Format: (dept, task_type) -> {agent: (sim_sr, sim_lat_ms, sim_conf)}
SIMULATOR_TASK_UTILITIES: Dict[Tuple[str, str], Dict[str, Tuple[float, float, float]]] = {
    # ── Sales ─────────────────────────────────────────────────────────────────
    ("sales", "lead_search"): {
        "sales_outreach_fast": (0.85, 800.0, 0.90),        # Has search_leads (800ms)
        "sales_enterprise_thorough": (0.85, 800.0, 0.90),  # Has search_leads (800ms)
    },
    ("sales", "outreach_drafting"): {
        "sales_outreach_fast": (0.90, 1200.0, 0.85),       # Has draft_outreach (1200ms)
        "sales_enterprise_thorough": (0.90, 1200.0, 0.85),
    },
    ("sales", "crm_update"): {
        "sales_outreach_fast": (0.80, 500.0, 0.95),        # Has update_crm (500ms)
        "sales_enterprise_thorough": (0.80, 500.0, 0.95),
    },
    ("sales", "pipeline_analysis"): {
        "sales_outreach_fast": (0.0, 0.0, 0.0),            # Lacks analyze_pipeline (Execution failure)
        "sales_enterprise_thorough": (0.75, 1500.0, 0.80), # Has analyze_pipeline (1500ms)
    },
    ("sales", "deal_qualification"): {
        "sales_outreach_fast": (0.0, 0.0, 0.0),            # Lacks qualify_deal (Execution failure)
        "sales_enterprise_thorough": (0.88, 900.0, 0.85),  # Has qualify_deal (900ms)
    },

    # ── Support ───────────────────────────────────────────────────────────────
    ("support", "ticket_triage"): {
        "support_tier1_fast": (0.90, 600.0, 0.90),         # Has triage_ticket (600ms)
        "support_tier2_specialist": (0.90, 600.0, 0.90),
    },
    ("support", "response_drafting"): {
        "support_tier1_fast": (0.88, 1400.0, 0.80),        # Has draft_response (1400ms)
        "support_tier2_specialist": (0.88, 1400.0, 0.80),
    },
    ("support", "ticket_escalation"): {
        "support_tier1_fast": (0.92, 400.0, 0.95),         # Has escalate (400ms)
        "support_tier2_specialist": (0.92, 400.0, 0.95),
    },
    ("support", "sentiment_analysis"): {
        "support_tier1_fast": (0.0, 0.0, 0.0),             # Lacks analyze_sentiment
        "support_tier2_specialist": (0.82, 1000.0, 0.75),  # Has analyze_sentiment
    },
    ("support", "csat_analysis"): {
        "support_tier1_fast": (0.0, 0.0, 0.0),             # Lacks get_csat_summary
        "support_tier2_specialist": (0.78, 1200.0, 0.85),  # Has get_csat_summary
    },

    # ── Research ──────────────────────────────────────────────────────────────
    ("research", "data_query"): {
        "research_kpi_quick": (0.80, 1800.0, 0.85),        # Has query_data (1800ms)
        "research_deep_analyst": (0.80, 1800.0, 0.85),
    },
    ("research", "trend_analysis"): {
        "research_kpi_quick": (0.82, 2200.0, 0.80),        # Has analyze_trends (2200ms)
        "research_deep_analyst": (0.82, 2200.0, 0.80),
    },
    ("research", "report_generation"): {
        "research_kpi_quick": (0.85, 2000.0, 0.75),        # Has generate_report (2000ms)
        "research_deep_analyst": (0.85, 2000.0, 0.75),
    },
    ("research", "segment_comparison"): {
        "research_kpi_quick": (0.0, 0.0, 0.0),             # Lacks compare_segments
        "research_deep_analyst": (0.78, 2500.0, 0.80),     # Has compare_segments
    },
    ("research", "churn_detection"): {
        "research_kpi_quick": (0.0, 0.0, 0.0),             # Lacks detect_churn_signals
        "research_deep_analyst": (0.75, 2800.0, 0.70),     # Has detect_churn_signals
    },
}


def _calculate_utility(sr: float, lat_ms: float, conf: float) -> float:
    """Calculate utility matching the ABOS evaluation scoring formula."""
    if sr <= 0.0:
        return 0.0
    lat_score = 1.0 / (1.0 + lat_ms / 3000.0)
    return 0.50 * sr + 0.20 * lat_score + 0.30 * conf


# Compute deterministic optimal agent per task from simulator utility
ORACLE_OPTIMAL_ROUTING: Dict[Tuple[str, str], str] = {}
for task_key, candidates in SIMULATOR_TASK_UTILITIES.items():
    best_agent = max(
        candidates.keys(),
        key=lambda agent: _calculate_utility(*candidates[agent]),
    )
    ORACLE_OPTIMAL_ROUTING[task_key] = best_agent


def get_oracle_optimal_agent(department: str, task_type: str) -> str:
    """Return the utility-maximizing oracle agent for a department and task type."""
    key = (department.lower(), task_type.lower())
    if key in ORACLE_OPTIMAL_ROUTING:
        return ORACLE_OPTIMAL_ROUTING[key]
    return f"{department}_agent"
