"""
ABOS vs Static Baseline — Paired Evaluation Experiment Runner.

Executes controlled, paired experimental trials across 9 canonical business scenarios:
  - Experiment A (Cold-Start Mode): Empty initial profiles (0.41 prior).
  - Experiment B (Warm Benchmark Mode): Fixed, frozen empirical profile snapshot (N >= 3).

Both systems share identical seeds, prompt decomposition, and memory conditions per trial.
The Static Baseline strictly ignores profile data and executes fixed departmental routing.
"""

import asyncio
import argparse
import logging
from typing import Dict, List, Any, Optional
from unittest.mock import patch, AsyncMock, MagicMock

from evaluation.scenarios import SCENARIOS, SCENARIO_IDS
from evaluation.oracle import get_oracle_optimal_agent
from evaluation.metrics import compute_metrics, TrialMetrics, aggregate
from evaluation.compare import compare_scenario_trials, ScenarioComparisonResult
from backend.agents.department.mock_simulator import set_simulator, MockSimulator
from backend.agents.graph import build_graph
from evaluation.baseline import build_baseline_graph

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
logger = logging.getLogger("evaluation_runner")

# 7 Fixed seeds per scenario for reproducible paired trials
TRIAL_SEEDS: List[int] = [1042, 2187, 3951, 4820, 5714, 6932, 7819]


class MockDBProfile:
    def __init__(self, name: str, dept: str, sr: float, lat: float, conf: float, total: int, task_type: Optional[str] = None):
        self.agent_name = name
        self.department = dept
        self.success_rate = sr
        self.avg_latency_ms = lat
        self.confidence_score = conf
        self.total_executions = total
        self.task_type = task_type


# Fixed frozen warm-up snapshot for Experiment B (Warm Benchmark)
# Grounded in empirical trials; frozen across all scenario runs with zero inter-trial mutation
FROZEN_WARM_PROFILES = {
    # Task-Specific Profiles (N >= 3)
    "task_profiles": [
        MockDBProfile("sales_outreach_fast", "sales", 0.85, 800.0, 0.85, 10, "lead_search"),
        MockDBProfile("sales_outreach_fast", "sales", 0.90, 1200.0, 0.88, 10, "outreach_drafting"),
        MockDBProfile("sales_outreach_fast", "sales", 0.80, 500.0, 0.90, 10, "crm_update"),
        MockDBProfile("sales_enterprise_thorough", "sales", 0.75, 1500.0, 0.80, 10, "pipeline_analysis"),
        MockDBProfile("sales_enterprise_thorough", "sales", 0.88, 900.0, 0.86, 10, "deal_qualification"),

        MockDBProfile("support_tier1_fast", "support", 0.90, 600.0, 0.88, 10, "ticket_triage"),
        MockDBProfile("support_tier1_fast", "support", 0.88, 1400.0, 0.82, 10, "response_drafting"),
        MockDBProfile("support_tier1_fast", "support", 0.92, 400.0, 0.90, 10, "ticket_escalation"),
        MockDBProfile("support_tier2_specialist", "support", 0.82, 1000.0, 0.80, 10, "sentiment_analysis"),
        MockDBProfile("support_tier2_specialist", "support", 0.78, 1200.0, 0.82, 10, "csat_analysis"),

        MockDBProfile("research_kpi_quick", "research", 0.80, 1800.0, 0.82, 10, "data_query"),
        MockDBProfile("research_kpi_quick", "research", 0.82, 2200.0, 0.80, 10, "trend_analysis"),
        MockDBProfile("research_kpi_quick", "research", 0.85, 2000.0, 0.78, 10, "report_generation"),
        MockDBProfile("research_deep_analyst", "research", 0.78, 2500.0, 0.80, 10, "segment_comparison"),
        MockDBProfile("research_deep_analyst", "research", 0.75, 2800.0, 0.75, 10, "churn_detection"),
    ],
    # Aggregate Profiles (N >= 1)
    "agg_profiles": [
        MockDBProfile("sales_outreach_fast", "sales", 0.85, 833.0, 0.87, 30),
        MockDBProfile("sales_enterprise_thorough", "sales", 0.81, 1200.0, 0.83, 20),
        MockDBProfile("support_tier1_fast", "support", 0.90, 800.0, 0.86, 30),
        MockDBProfile("support_tier2_specialist", "support", 0.80, 1100.0, 0.81, 20),
        MockDBProfile("research_kpi_quick", "research", 0.82, 2000.0, 0.80, 30),
        MockDBProfile("research_deep_analyst", "research", 0.76, 2650.0, 0.77, 20),
    ],
}


async def run_single_trial(
    graph: Any,
    scenario: Dict[str, Any],
    scenario_id: str,
    system: str,
    trial_number: int,
    seed: int,
    mode: str = "cold",
) -> TrialMetrics:
    """Run a single isolated trial for a given graph and seed."""
    set_simulator(MockSimulator(seed=seed))

    initial_state = {
        "goal_id": f"eval-{system}-{scenario_id}-t{trial_number}-s{seed}",
        "workflow_id": f"eval-wf-{system}-{scenario_id}-t{trial_number}",
        "user_id": "eval-runner",
        "goal_title": scenario["title"],
        "goal_description": scenario["description"],
        "goal_priority": scenario.get("priority", "medium"),
        "goal_context": {"system": system, "scenario_id": scenario_id, "seed": seed, "mode": mode},
        "target_departments": scenario.get("target_departments"),
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

    # Hermetic database mocking per trial to guarantee zero inter-trial cross-contamination
    with patch("backend.db.session.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session

        async def mock_execute(stmt):
            stmt_str = str(stmt)
            res = MagicMock()
            if mode == "cold":
                # Cold mode: empty profiles -> resolves to 0.41 prior
                res.scalars.return_value.all.return_value = []
            else:
                # Warm mode: returns frozen benchmark snapshot
                if "agent_task_profiles" in stmt_str:
                    res.scalars.return_value.all.return_value = FROZEN_WARM_PROFILES["task_profiles"]
                else:
                    res.scalars.return_value.all.return_value = FROZEN_WARM_PROFILES["agg_profiles"]
            return res

        mock_session.execute = mock_execute

        try:
            result = await graph.ainvoke(initial_state)
        except Exception as e:
            logger.error(f"[{system.upper()} {scenario_id} t{trial_number}] Graph execution failed: {e}")
            result = dict(initial_state)
            result["final_status"] = "failed"
            result["error"] = str(e)

    return compute_metrics(
        result=result,
        scenario_id=scenario_id,
        system=system,
        trial_number=trial_number,
        seed=seed,
    )


async def run_scenario_experiment(
    scenario_id: str,
    mode: str = "cold",
    n_trials: int = 7,
) -> ScenarioComparisonResult:
    """Run n paired trials for one scenario between ABOS and Baseline."""
    scenario = SCENARIOS[scenario_id]
    seeds = TRIAL_SEEDS[:n_trials]

    abos_graph = build_graph()
    baseline_graph = build_baseline_graph()

    abos_trials: List[TrialMetrics] = []
    baseline_trials: List[TrialMetrics] = []

    for i, seed in enumerate(seeds, 1):
        # 1. Run ABOS trial
        abos_m = await run_single_trial(
            graph=abos_graph,
            scenario=scenario,
            scenario_id=scenario_id,
            system="abos",
            trial_number=i,
            seed=seed,
            mode=mode,
        )
        abos_trials.append(abos_m)

        # 2. Run Baseline trial with exact same seed
        base_m = await run_single_trial(
            graph=baseline_graph,
            scenario=scenario,
            scenario_id=scenario_id,
            system="baseline",
            trial_number=i,
            seed=seed,
            mode=mode,
        )
        baseline_trials.append(base_m)

    return compare_scenario_trials(
        scenario_id=scenario_id,
        abos_trials=abos_trials,
        baseline_trials=baseline_trials,
    )


def print_comparison_table(results: List[ScenarioComparisonResult], mode: str):
    """Format and print the comparative experimental results."""
    print("\n" + "=" * 105)
    print(f"ABOS vs STATIC BASELINE: PAIRED EVALUATION EXPERIMENTAL RESULTS [Mode: {mode.upper()}]")
    print("=" * 105)
    print(
        f"{'Scenario':<8} | {'ABOS TCR (mean±sd)':<18} | {'Base TCR (mean±sd)':<18} | "
        f"{'Δ TCR':<8} | {'Pairs (nz)':<10} | {'Wilcoxon W':<10} | {'p-value':<8} | {'Rank-Biserial':<12}"
    )
    print("-" * 105)

    tcr_deltas = []
    lat_deltas = []
    oa_deltas = []

    for r in results:
        tcr_deltas.append(r.tcr_delta_mean)
        lat_deltas.append(r.latency_delta_mean)
        oa_deltas.append(r.oracle_agreement_delta_mean)

        abos_tcr_str = f"{r.abos_tcr_mean*100:.1f}% ± {r.abos_tcr_std*100:.1f}%"
        base_tcr_str = f"{r.base_tcr_mean*100:.1f}% ± {r.base_tcr_std*100:.1f}%"
        delta_str = f"{'+' if r.tcr_delta_mean >= 0 else ''}{r.tcr_delta_mean*100:.1f}%"
        pair_str = f"{r.n_pairs} ({r.n_nonzero_tcr})"

        print(
            f"{r.scenario_id:<8} | {abos_tcr_str:<18} | {base_tcr_str:<18} | "
            f"{delta_str:<8} | {pair_str:<10} | {r.tcr_wilcoxon_stat:<10.1f} | {r.tcr_p_value:<8.4f} | {r.tcr_rank_biserial:<12.4f}"
        )
        if r.note:
            print(f"   ↳ Note: {r.note}")

    print("-" * 105)
    avg_tcr_delta = (sum(tcr_deltas) / len(tcr_deltas)) * 100
    avg_oa_delta = (sum(oa_deltas) / len(oa_deltas)) * 100
    avg_lat_delta = sum(lat_deltas) / len(lat_deltas)

    print(f"\nOVERALL DESCRIPTIVE RESULTS ACROSS {len(results)} SCENARIOS ({len(results) * 7} PAIRED TRIALS):")
    print(f"  - Primary: Mean Task Completion Rate Delta (Δ TCR)   : {'+' if avg_tcr_delta >= 0 else ''}{avg_tcr_delta:.2f} percentage points")
    print(f"  - Primary: Mean Step Latency Delta (Δ Step Latency) : {'+' if avg_lat_delta >= 0 else ''}{avg_lat_delta:.1f} ms")
    print(f"  - Secondary: Mean Oracle Agreement Delta (Δ Oracle) : {'+' if avg_oa_delta >= 0 else ''}{avg_oa_delta:.2f} percentage points")
    print("=" * 105 + "\n")


async def main():
    parser = argparse.ArgumentParser(description="Run ABOS vs Baseline Evaluation Trials")
    parser.add_argument("--mode", type=str, required=True, choices=["cold", "warm"], help="Evaluation Mode: 'cold' or 'warm'")
    parser.add_argument("--scenario", type=str, default="all", help="Scenario ID (e.g. S1, P1, R1) or 'all'")
    parser.add_argument("--trials", type=int, default=7, help="Number of paired trials per scenario (default: 7)")
    args = parser.parse_args()

    scenarios_to_run = SCENARIO_IDS if args.scenario == "all" else [args.scenario.upper()]

    results: List[ScenarioComparisonResult] = []
    print(f"\nStarting Evaluation Runner: {len(scenarios_to_run)} scenarios, {args.trials} paired trials per scenario (Mode: {args.mode})...")

    for sid in scenarios_to_run:
        print(f"  Running scenario {sid} ({SCENARIOS[sid]['title']})...")
        res = await run_scenario_experiment(scenario_id=sid, mode=args.mode, n_trials=args.trials)
        results.append(res)

    print_comparison_table(results, mode=args.mode)


if __name__ == "__main__":
    asyncio.run(main())
