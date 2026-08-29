"""
Statistical Comparison Module — Wilcoxon Signed-Rank Test & Effect Sizes.

Performs paired non-parametric statistical hypothesis testing per scenario
and generates aggregate descriptive summaries.
"""

from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
from scipy import stats

from evaluation.metrics import TrialMetrics, AggregatedMetrics, aggregate


@dataclass
class ScenarioComparisonResult:
    """Statistical comparison results for one scenario across paired trials."""
    scenario_id: str
    n_pairs: int
    n_nonzero_tcr: int
    n_nonzero_latency: int

    # TCR Comparison (Primary)
    abos_tcr_mean: float
    abos_tcr_std: float
    abos_tcr_median: float
    base_tcr_mean: float
    base_tcr_std: float
    base_tcr_median: float
    tcr_delta_mean: float           # ABOS - Baseline (percentage points)
    tcr_wilcoxon_stat: float
    tcr_p_value: float
    tcr_rank_biserial: float        # Exact Rank-Biserial Correlation r_rb in [-1, 1]

    # Latency Comparison (Primary)
    abos_latency_mean: float
    base_latency_mean: float
    latency_delta_mean: float       # ABOS - Baseline (ms)
    latency_wilcoxon_stat: float
    latency_p_value: float
    latency_rank_biserial: float

    # Oracle Agreement Comparison (Secondary Diagnostic)
    abos_oracle_agreement_mean: float
    base_oracle_agreement_mean: float
    oracle_agreement_delta_mean: float

    # Statistical validity caveat note
    note: Optional[str] = None


def _compute_wilcoxon_and_rank_biserial(a_vals: List[float], b_vals: List[float]) -> Tuple[float, float, float, int]:
    """
    Compute Wilcoxon signed-rank test and exact matched-pairs rank-biserial correlation.
    Returns: (W_statistic, p_value, rank_biserial_r, n_nonzero)
    """
    diffs = [a - b for a, b in zip(a_vals, b_vals)]
    nonzero_diffs = [d for d in diffs if d != 0]
    n_nonzero = len(nonzero_diffs)

    if n_nonzero == 0:
        return 0.0, 1.0, 0.0, 0

    try:
        # Wilcoxon test with Pratt zero-method to handle ties
        res = stats.wilcoxon(a_vals, b_vals, zero_method="pratt")
        w_stat = float(res.statistic)
        p_val = float(res.pvalue)

        # Rank-Biserial Correlation r_rb = (W+ - W-) / (W+ + W-)
        # Sum of positive ranks vs negative ranks
        ranked_data = []
        for d in nonzero_diffs:
            ranked_data.append((abs(d), 1 if d > 0 else -1))
        ranked_data.sort(key=lambda x: x[0])

        # Assign average ranks for ties
        w_plus = 0.0
        w_minus = 0.0
        n_nz = len(ranked_data)

        i = 0
        while i < n_nz:
            j = i
            while j < n_nz and ranked_data[j][0] == ranked_data[i][0]:
                j += 1
            avg_rank = (i + 1 + j) / 2.0
            for k in range(i, j):
                if ranked_data[k][1] > 0:
                    w_plus += avg_rank
                else:
                    w_minus += avg_rank
            i = j

        w_total = w_plus + w_minus
        r_rb = (w_plus - w_minus) / w_total if w_total > 0 else 0.0
        return round(w_stat, 2), round(p_val, 4), round(r_rb, 4), n_nonzero

    except Exception:
        return 0.0, 1.0, 0.0, n_nonzero


def compare_scenario_trials(
    scenario_id: str,
    abos_trials: List[TrialMetrics],
    baseline_trials: List[TrialMetrics],
) -> ScenarioComparisonResult:
    """
    Compare paired trials for a single scenario.
    Assumes abos_trials[i] and baseline_trials[i] share the exact same seed.
    """
    if len(abos_trials) != len(baseline_trials):
        raise ValueError(f"Mismatched trial count: {len(abos_trials)} vs {len(baseline_trials)}")

    n = len(abos_trials)
    abos_agg = aggregate(abos_trials)
    base_agg = aggregate(baseline_trials)

    tcr_abos = [t.task_completion_rate for t in abos_trials]
    tcr_base = [t.task_completion_rate for t in baseline_trials]
    tcr_diffs = [a - b for a, b in zip(tcr_abos, tcr_base)]
    tcr_delta = sum(tcr_diffs) / n

    lat_abos = [t.avg_step_latency_ms for t in abos_trials]
    lat_base = [t.avg_step_latency_ms for t in baseline_trials]
    lat_diffs = [a - b for a, b in zip(lat_abos, lat_base)]
    lat_delta = sum(lat_diffs) / n

    w_stat_tcr, p_val_tcr, r_rb_tcr, n_nz_tcr = _compute_wilcoxon_and_rank_biserial(tcr_abos, tcr_base)
    w_stat_lat, p_val_lat, r_rb_lat, n_nz_lat = _compute_wilcoxon_and_rank_biserial(lat_abos, lat_base)

    note = None
    if n_nz_tcr < 5 and n_nz_tcr > 0:
        note = "Interpretation is limited because few paired differences are non-zero."

    oa_abos = abos_agg.oracle_agreement_mean
    oa_base = base_agg.oracle_agreement_mean
    oa_delta = round(oa_abos - oa_base, 4)

    return ScenarioComparisonResult(
        scenario_id=scenario_id,
        n_pairs=n,
        n_nonzero_tcr=n_nz_tcr,
        n_nonzero_latency=n_nz_lat,
        abos_tcr_mean=abos_agg.tcr_mean,
        abos_tcr_std=abos_agg.tcr_std,
        abos_tcr_median=abos_agg.tcr_median,
        base_tcr_mean=base_agg.tcr_mean,
        base_tcr_std=base_agg.tcr_std,
        base_tcr_median=base_agg.tcr_median,
        tcr_delta_mean=round(tcr_delta, 4),
        tcr_wilcoxon_stat=w_stat_tcr,
        tcr_p_value=p_val_tcr,
        tcr_rank_biserial=r_rb_tcr,
        abos_latency_mean=abos_agg.avg_latency_mean,
        base_latency_mean=base_agg.avg_latency_mean,
        latency_delta_mean=round(lat_delta, 2),
        latency_wilcoxon_stat=w_stat_lat,
        latency_p_value=p_val_lat,
        latency_rank_biserial=r_rb_lat,
        abos_oracle_agreement_mean=oa_abos,
        base_oracle_agreement_mean=oa_base,
        oracle_agreement_delta_mean=oa_delta,
        note=note,
    )
