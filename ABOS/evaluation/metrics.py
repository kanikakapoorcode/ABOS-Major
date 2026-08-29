"""
Evaluation metrics computation.

Computes evaluation metrics for both ABOS and Baseline runs.
Oracle agreement rate evaluates post-hoc agreement against the utility-maximizing Simulator Oracle.
All metric calculations are pure and deterministic.
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from evaluation.oracle import get_oracle_optimal_agent


@dataclass
class TrialMetrics:
    """Computed metrics for one trial run (ABOS or Baseline)."""
    scenario_id: str
    system: str                      # "abos" or "baseline"
    trial_number: int
    seed: int

    # ── Primary metrics ────────────────────────────────────────────────────────
    task_completion_rate: float      # completed_steps / total_steps (0.0 - 1.0)
    avg_step_latency_ms: float       # sum(executed_step_latencies) / executed_step_count
    total_scenario_latency_ms: float # sum(executed_step_latencies)
    recovery_success_rate: Optional[float] # recovered / total_failed_attempts (None if 0 failures)

    # ── Secondary diagnostics ──────────────────────────────────────────────────
    oracle_agreement_rate: float     # oracle_matched_steps / total_conditioned_steps (0.0 - 1.0)
    scheduler_score_correlation: Optional[float]  # Pearson r(score, success), None for baseline

    # ── Counts ─────────────────────────────────────────────────────────────────
    total_steps: int
    completed_steps: int
    failed_steps: int
    recovered_steps: int
    executed_steps: int

    # ── Raw traces for statistical tests ───────────────────────────────────────
    step_latencies: List[float] = field(default_factory=list)
    step_successes: List[int] = field(default_factory=list)   # 1=success, 0=fail
    scheduler_scores: List[float] = field(default_factory=list)
    assigned_agents: List[str] = field(default_factory=list)
    oracle_agents: List[str] = field(default_factory=list)


def compute_metrics(
    result: Dict[str, Any],
    scenario_id: str,
    system: str,
    trial_number: int,
    seed: int,
) -> TrialMetrics:
    """
    Compute all evaluation metrics from a completed graph result state.
    """
    plan: List[Dict] = result.get("workflow_plan") or []
    completed: List[Dict] = result.get("completed_steps") or []
    failed: List[Dict] = result.get("failed_steps") or []

    total = len(plan)
    n_completed = len(completed)
    n_failed = len(failed)

    # 1. Task Completion Rate (TCR)
    tcr = n_completed / total if total > 0 else 0.0

    # 2. Recovery Success Rate (RSR)
    # A step is "recovered" if it appears in completed_steps but had retry_count > 0
    recovered = sum(1 for s in completed if s.get("retry_count", 0) > 0)
    total_failed_attempts = n_failed + recovered
    rsr = (recovered / total_failed_attempts) if total_failed_attempts > 0 else None

    # 3. Latency Metrics
    latencies = [
        s["latency_ms"] for s in plan
        if s.get("latency_ms") is not None
    ]
    executed_count = len(latencies)
    avg_step_lat = (sum(latencies) / executed_count) if executed_count > 0 else 0.0
    total_scenario_lat = sum(latencies)

    # 4. Oracle Agreement Rate (Secondary Diagnostic)
    oracle_matches = 0
    conditioned_count = 0
    assigned_list = []
    oracle_list = []

    for s in plan:
        dept = s.get("assigned_department", "sales")
        task_type = s.get("task_type")
        assigned = s.get("assigned_agent", "")
        assigned_list.append(assigned)

        if task_type:
            oracle_agent = get_oracle_optimal_agent(dept, task_type)
            oracle_list.append(oracle_agent)
            conditioned_count += 1
            if assigned == oracle_agent:
                oracle_matches += 1
        else:
            oracle_list.append("unconditioned")

    oracle_agreement = (oracle_matches / conditioned_count) if conditioned_count > 0 else 0.0

    # 5. Scheduler Score Correlation (Secondary Diagnostic)
    scores = [s.get("scheduler_score") for s in plan if s.get("scheduler_score") is not None]
    successes = [1 if s.get("status") == "completed" else 0 for s in plan if s.get("scheduler_score") is not None]
    score_corr = _pearson_r(scores, successes) if len(scores) >= 3 else None

    return TrialMetrics(
        scenario_id=scenario_id,
        system=system,
        trial_number=trial_number,
        seed=seed,
        task_completion_rate=round(tcr, 4),
        oracle_agreement_rate=round(oracle_agreement, 4),
        avg_step_latency_ms=round(avg_step_lat, 2),
        total_scenario_latency_ms=round(total_scenario_lat, 2),
        recovery_success_rate=round(rsr, 4) if rsr is not None else None,
        scheduler_score_correlation=round(score_corr, 4) if score_corr is not None else None,
        total_steps=total,
        completed_steps=n_completed,
        failed_steps=n_failed,
        recovered_steps=recovered,
        executed_steps=executed_count,
        step_latencies=latencies,
        step_successes=[1 if s.get("status") == "completed" else 0 for s in plan],
        scheduler_scores=scores,
        assigned_agents=assigned_list,
        oracle_agents=oracle_list,
    )


def _pearson_r(x: List[float], y: List[float]) -> Optional[float]:
    """Compute Pearson correlation coefficient between two lists."""
    n = len(x)
    if n < 2:
        return None
    mx = sum(x) / n
    my = sum(y) / n
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    den_x = (sum((xi - mx) ** 2 for xi in x)) ** 0.5
    den_y = (sum((yi - my) ** 2 for yi in y)) ** 0.5
    if den_x == 0 or den_y == 0:
        return None
    return num / (den_x * den_y)


@dataclass
class AggregatedMetrics:
    """Descriptive statistics across trials for one (scenario, system) pair."""
    scenario_id: str
    system: str
    n_trials: int

    tcr_mean: float
    tcr_std: float
    tcr_median: float

    oracle_agreement_mean: float
    oracle_agreement_std: float
    oracle_agreement_median: float

    avg_latency_mean: float
    avg_latency_std: float

    total_latency_mean: float
    total_latency_std: float

    rsr_mean: Optional[float]
    rsr_std: Optional[float]


def aggregate(trials: List[TrialMetrics]) -> AggregatedMetrics:
    """Aggregate a list of TrialMetrics into mean, std, and median."""
    if not trials:
        raise ValueError("No trials to aggregate.")

    def _stats(values: List[float]):
        if not values:
            return 0.0, 0.0, 0.0
        n = len(values)
        mean = sum(values) / n
        std = (sum((v - mean) ** 2 for v in values) / n) ** 0.5
        sorted_vals = sorted(values)
        median = (
            sorted_vals[n // 2]
            if n % 2 != 0
            else (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2.0
        )
        return round(mean, 4), round(std, 4), round(median, 4)

    tcr_m, tcr_s, tcr_med = _stats([t.task_completion_rate for t in trials])
    oa_m, oa_s, oa_med = _stats([t.oracle_agreement_rate for t in trials])
    lat_m, lat_s, _ = _stats([t.avg_step_latency_ms for t in trials])
    tot_lat_m, tot_lat_s, _ = _stats([t.total_scenario_latency_ms for t in trials])

    valid_rsrs = [t.recovery_success_rate for t in trials if t.recovery_success_rate is not None]
    if valid_rsrs:
        rsr_m, rsr_s, _ = _stats(valid_rsrs)
    else:
        rsr_m, rsr_s = None, None

    return AggregatedMetrics(
        scenario_id=trials[0].scenario_id,
        system=trials[0].system,
        n_trials=len(trials),
        tcr_mean=tcr_m,
        tcr_std=tcr_s,
        tcr_median=tcr_med,
        oracle_agreement_mean=oa_m,
        oracle_agreement_std=oa_s,
        oracle_agreement_median=oa_med,
        avg_latency_mean=lat_m,
        avg_latency_std=lat_s,
        total_latency_mean=tot_lat_m,
        total_latency_std=tot_lat_s,
        rsr_mean=rsr_m,
        rsr_std=rsr_s,
    )
