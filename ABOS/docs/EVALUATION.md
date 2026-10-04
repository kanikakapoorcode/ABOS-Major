# ABOS — Evaluation Guide

This document describes the evaluation protocol for the research contribution.

---

## What We're Evaluating

ABOS is evaluated against a **static-workflow baseline** — a system that uses a fixed routing hierarchy (like Autonoma's fixed pipeline) with no adaptive scheduling.

This directly mirrors the evaluation methodology used in Self-Healing Orchestrators (2026) and Agentic ERP (2026), making results legible to reviewers who know this literature.

---

## Metrics

| Metric | Definition | How Measured |
|---|---|---|
| **Task Completion Rate** | % of workflow steps completed successfully | `completed_steps / total_steps` |
| **Routing Accuracy** | % of steps routed to the department feedback confirms was correct | `steps_with_no_correction / steps_with_feedback` |
| **Recovery Success Rate** | % of initially-failed steps that were recovered | `recovered_steps / failed_steps` |
| **Average Latency** | Mean time per step execution (ms) | Logged in `executions.latency_ms` |
| **Scheduler Score Correlation** | Correlation between scheduler score and actual success | Pearson r on (scheduler_score, success) pairs |

---

## Test Scenarios

### Sales Department
1. Q4 Enterprise Lead Outreach — identify and contact 20 cold enterprise leads
2. Pipeline Health Check — summarize pipeline and flag at-risk deals
3. Competitive Win/Loss Analysis — analyze last 30 closed deals

### Customer Support Department
1. Ticket Backlog Triage — classify and prioritize 50 open tickets
2. Escalation Review — identify tickets requiring human escalation
3. CSAT Improvement Plan — analyze low-rated tickets and draft improvement actions

### Research & Analytics Department
1. Market Segment Analysis — compare two customer segments by engagement
2. Monthly Performance Report — generate KPI summary report
3. Churn Prediction Input — identify behavioural signals of at-risk customers

---

## Baseline System

The static baseline uses:
- Fixed department assignment (no scheduler — round-robin or priority order)
- No memory layer (no feedback retrieval)
- Same recovery module as ABOS (so recovery is not a confounding factor)

This isolates the contribution of: (a) adaptive workflow generation, and (b) performance-based scheduling.

---

## Running the Evaluation

```bash
# Run full evaluation suite (logs results to MLflow)
poetry run python evaluation/run_evaluation.py

# Run a specific scenario
poetry run python evaluation/run_evaluation.py --scenario sales_outreach

# Run baseline only
poetry run python evaluation/run_evaluation.py --mode baseline

# Compare ABOS vs baseline
poetry run python evaluation/compare.py
```

All runs are logged to MLflow. View at http://localhost:5000.

---

## Ablation Studies

Run ablation studies to measure the contribution of each component:

| Ablation | What's disabled | Purpose |
|---|---|---|
| No scheduler | Random routing | Measures scheduler contribution |
| No memory | No feedback retrieval | Measures memory layer contribution |
| No recovery | No retry/reroute | Measures recovery module contribution |
| Static workflow | Fixed plan, no LLM decomposition | Measures planner contribution |

```bash
poetry run python evaluation/ablation.py --ablation no_scheduler
poetry run python evaluation/ablation.py --ablation no_memory
poetry run python evaluation/ablation.py --ablation no_recovery
poetry run python evaluation/ablation.py --ablation static_workflow
```

---

## Reporting Results

Results are saved to `evaluation/results/` as CSV files and logged to MLflow.

For the paper, report:
- Mean ± std over 3 runs for each metric
- Statistical significance (Wilcoxon signed-rank test, p < 0.05) for key comparisons
- Tables formatted for LaTeX (use `evaluation/export_latex.py`)
