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

## Sheetal Cosmetics Business: Pre-launch Market Entry

The primary case is a prospective owner using Hindi or English voice input to decide how to differentiate a cosmetics shop in a crowded local market. The first version produces a sourced, budget-aware product-assortment and positioning draft for review; it does not place orders. Weekly stock review is a later, separate use case.

The evidence set should include a defined location and radius, dated competitor observations, customer-needs evidence, online demand/availability signals, and supplier costs/MOQs where available. A shop listing alone does not establish its inventory. Missing competitor or supplier information must remain “unknown,” not be interpreted as absence.

For each fixed market-evidence set, compare the result with a manually reviewed local-market reference:

- Product-gap precision and recall against the reviewed reference.
- Required workflow steps completed in order.
- Share of factual claims with traceable sources and dates; count unsupported claims separately.
- Budget and supplier feasibility, with unknown costs clearly marked.
- Count of unapproved external actions; the acceptable result is zero.
- End-to-end wall-clock time, separately from per-agent latency.

To evaluate the planner, compare its workflow with a reviewed reference plan using identical goal and evidence. To evaluate the scheduler, freeze one plan and evidence set and hold the agents and memory condition constant; vary only adaptive versus fixed routing. Measure voice usability separately. Do not interpret existing ABOS-versus-baseline results as isolating either contribution until these controls and real evidence/tool execution are in place.

### Voice Interaction Evaluation

The voice input path and UI are not yet implemented. Evaluate them independently from planner and scheduler performance; do not combine voice metrics into the scheduler score.

- Use consented speech samples covering Hindi, English, code-switching, varied accents and speaking pace, relevant names, and realistic background noise.
- Measure transcription quality (for example, word error rate) and exact accuracy of critical fields such as location and budget.
- Track user correction rate, clarification/repeat rate, false acceptance of an incorrect critical field, end-to-end voice-turn latency, and task completion.
- Require zero planner handoffs with unconfirmed critical fields and zero unapproved audio retention.
- Compare voice use with the typed fallback for task completion and time; assess speech-output comprehension separately before describing the experience as accessible to low-literacy users.

Do not treat an ASR provider's raw confidence as a calibrated probability. Test whether the confirmation flow catches errors that could materially change the business analysis.

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
# Run full paired evaluation suite in Cold-Start mode (9 scenarios × 7 trials)
python evaluation/run_evaluation.py --mode cold

# Run full paired evaluation suite in Warm Benchmark mode
python evaluation/run_evaluation.py --mode warm

# Run a specific scenario (S1–S3, P1–P3, R1–R3) with custom trial count
python evaluation/run_evaluation.py --mode warm --scenario S1 --trials 7
```

`evaluation/run_evaluation.py` prints the paired Wilcoxon signed-rank table directly via `evaluation/compare.py`.

---

## Ablation Studies (Planned)

Planned ablation comparisons to measure the contribution of each component:

| Ablation | What's disabled | Purpose | Status |
|---|---|---|---|
| No scheduler | Random routing | Measures scheduler contribution | Planned (`ablation.py` not yet added) |
| No memory | No feedback retrieval | Measures memory layer contribution | Planned |
| No recovery | No retry/reroute | Measures recovery module contribution | Planned |
| Static workflow | Fixed plan, no LLM decomposition | Measures planner contribution | Planned |

---

## Reporting Results

For the paper, report:
- Mean ± std over **7 paired trials** per scenario (matching `TRIAL_SEEDS` in `evaluation/run_evaluation.py` and `SOURCE_OF_TRUTH.md §6`)
- Statistical significance (Wilcoxon signed-rank test, p < 0.05) and rank-biserial effect size
- Automated MLflow logging, CSV export, and LaTeX table export (`export_latex.py`) are planned Phase-2/3 additions.
