# ABOS — Implementation Source of Truth

> This is the single authoritative document for all implementation decisions.
> If code contradicts this document, the code is wrong.
> If you want to change something here, discuss with the team first, then update this file, then update the code.
>
> Last updated: August 16, 2026 — Kanika Kapoor

---

## 1. Research Identity

### What ABOS Is

A system that takes a **high-level business goal** as input and:
1. Decomposes it into a multi-step, multi-department executable workflow (Planner)
2. Routes each step to the best available agent using a heuristic performance-based scheduler (Scheduler)
3. Executes each step via a specialized department agent (Executor)
4. Learns from explicit feedback to improve future routing (Memory Layer)

### What ABOS Is Not

- Not a production CRM, ERP, or support desk
- Not a general-purpose task automation system (that's Autonoma)
- Not an RL-based scheduler (that's MetaAgent-X)
- Not a novel failure recovery system (adopted from Self-Healing Orchestrators 2026)
- Not a novel memory framework (implements Level-2 of Governance-by-Design 2026)

### The Research Question (verbatim — do not paraphrase in any writeup)

> "How can a multi-agent AI system translate a high-level business goal into an
> executable, multi-department workflow, and route sub-tasks to specialized agents
> using an interpretable, performance-based scheduling policy — without relying on
> either fixed pipelines or heavyweight RL training?"

### The Two Novel Contributions

| # | Contribution | What makes it novel |
|---|---|---|
| 1 | Goal-to-Workflow Planner | No prior system takes a business goal (not a prompt) and generates a structured multi-department execution plan |
| 2 | Interpretable Performance-Based Scheduler | No lightweight non-RL alternative exists for business-department agent routing |

### What Is Adopted (cite, never claim)

| Component | Source | Citation |
|---|---|---|
| Failure recovery | Self-Healing Agentic Orchestrators (2026) | arxiv 2606.01416 |
| Memory maturity model | Governance by Design (2026) | arxiv 2605.20210 |

---

## 2. System Architecture

### Component Map

```
User Goal (natural language)
        │
        ▼
  FastAPI  ──► Celery Task Queue (Redis)
                        │
                        ▼
              LangGraph Graph
              ┌─────────────────────────────────────┐
              │                                     │
              │  memory_retrieval                   │
              │       ↓                             │
              │   planner          [Contribution 1] │
              │       ↓                             │
              │  scheduler         [Contribution 2] │
              │       ↓                             │
              │  executor ──► department agent      │
              │       ↓ fail                        │
              │   recovery  (adopted, cited)        │
              │       ↓                             │
              │  summarizer                         │
              └─────────────────────────────────────┘
                        │
                        ▼
              PostgreSQL + pgvector
```

### Data Flow (one goal, end to end)

```
1. POST /api/v1/goals/          → goal created, status=pending
2. Celery: execute_goal_task    → status=planning
3. memory_retrieval node        → embed goal, fetch top-5 similar feedback
4. planner node                 → LLM decomposes goal into WorkflowStepState list
5. scheduler node               → score agents per step, assign best
6. executor node (loop)         → run each step via department agent
7. recovery node (on failure)   → classify → retry/reroute/skip
8. summarizer node              → LLM summary of run
9. DB write                     → workflow status, step outcomes, execution records
10. feedback (async)            → user corrects routing → profile update → embedding store
```

---

## 3. LangGraph State Contract

`ABOSState` is the single typed dict passed between all nodes.
**Nodes must only write fields they own. Never mutate fields owned by another node.**

| Field | Type | Owner | Description |
|---|---|---|---|
| `goal_id` | str | input | Immutable |
| `workflow_id` | str | input | Immutable |
| `user_id` | str | input | Immutable |
| `goal_title` | str | input | Immutable |
| `goal_description` | str | input | Immutable |
| `goal_priority` | str | input | Immutable |
| `goal_context` | dict | input | Immutable |
| `target_departments` | list | input | Hint only, planner may override |
| `workflow_plan` | List[WorkflowStepState] | planner → scheduler → executor | Each node may update steps in-place |
| `current_step_index` | int | executor / recovery | Incremented on success or skip |
| `completed_steps` | List[WorkflowStepState] | executor (operator.add) | Append-only |
| `failed_steps` | List[WorkflowStepState] | recovery (operator.add) | Append-only |
| `retrieved_memory` | list | memory_retrieval | Read by planner only |
| `recovery_attempts` | int | recovery | Reset to 0 when a new step starts |
| `max_recovery_attempts` | int | input | Default: 3 |
| `final_status` | str | summarizer | completed / failed / partially_completed |
| `summary` | str | summarizer | LLM-generated run summary |
| `error` | str | planner / executor | First fatal error message |
| `logs` | List[str] | all (operator.add) | Append-only audit trail |

### WorkflowStepState Fields

| Field | Type | Set by | Description |
|---|---|---|---|
| `step_index` | int | planner | 0-based |
| `title` | str | planner | Max 200 chars |
| `description` | str | planner | Max 1000 chars |
| `assigned_department` | str | planner | sales / support / research |
| `assigned_agent` | str | scheduler | sales_agent / support_agent / research_agent |
| `input_data` | dict | planner | Parameters for the agent |
| `output_data` | dict | executor | Agent's output |
| `status` | str | executor / recovery | pending / running / completed / failed / retrying / skipped |
| `retry_count` | int | recovery | Incremented on each retry |
| `latency_ms` | float | executor | Measured wall time |
| `scheduler_score` | float | scheduler | Composite score used for routing |
| `error_message` | str | executor | Last error string |

---

## 4. Scheduler — Full Specification

### Scoring Formula

```
score(agent) = W_sr * success_rate
             + W_lat * latency_score(avg_latency_ms)
             + W_conf * confidence_score
```

### Weights (locked — do not change without team discussion)

| Weight | Symbol | Value | Rationale |
|---|---|---|---|
| Success rate | W_sr | 0.50 | Primary signal — did the agent complete tasks? |
| Latency | W_lat | 0.20 | Secondary — prefer faster agents when scores are close |
| Confidence | W_conf | 0.30 | Feedback-adjusted — incorporates human corrections |

**These three signals are the complete scheduler. Token cost is NOT a scoring signal.**
Token cost is logged per execution (`executions.token_cost` field — add to model) for future analysis only. It does not affect routing decisions in v1.

### Latency Score Formula

```
latency_score(ms) = 1 / (1 + ms / 3000)
```

Reference point: 3000ms → score 0.5. 0ms → score 1.0. 9000ms → score 0.25.

### Confidence Score Update (after each execution + feedback)

```
new_confidence = (1 - α) * old_confidence + α * signal

signal = 1.0  if execution succeeded AND (no feedback OR feedback == "correct")
signal = 0.0  if execution failed OR feedback == "incorrect"
signal = 0.5  if feedback == "partial"

α (learning rate) = 0.1  (slow, stable adaptation)
```

### Rolling Window

- Window size: last **50 executions** per agent
- success_rate = successful executions in window / window size
- avg_latency_ms = mean latency of window

### Cold Start Values (agent has no history)

```
success_rate    = 1.0
avg_latency_ms  = 0.0   → latency_score = 1.0
confidence_score = 1.0
```

This gives new agents a score of 1.0 to encourage exploration. Decays naturally as real data accumulates.

---

## 5. Mock Tool Simulator — Controlled Variance Specification

**This is critical for evaluation validity.**
If tools always succeed with fixed latency, the scheduler has nothing to differentiate on and ABOS vs. baseline comparison will show near-identical results.

### Design

Each tool call goes through a `MockSimulator` that:
1. Draws success/failure from a **per-tool Bernoulli distribution**
2. Samples latency from a **per-tool normal distribution**
3. Occasionally injects a **low-confidence flag** in output

### Per-Tool Parameters

#### Sales Agent Tools

| Tool | Failure Rate | Latency mean (ms) | Latency std (ms) | Low-confidence rate |
|---|---|---|---|---|
| `search_leads` | 0.15 | 800 | 150 | 0.10 |
| `draft_outreach` | 0.10 | 1200 | 200 | 0.15 |
| `update_crm` | 0.20 | 500 | 100 | 0.05 |
| `analyze_pipeline` | 0.25 | 1500 | 300 | 0.20 |
| `qualify_deal` | 0.12 | 900 | 180 | 0.15 |

#### Support Agent Tools

| Tool | Failure Rate | Latency mean (ms) | Latency std (ms) | Low-confidence rate |
|---|---|---|---|---|
| `triage_ticket` | 0.10 | 600 | 120 | 0.10 |
| `draft_response` | 0.12 | 1400 | 250 | 0.20 |
| `escalate` | 0.08 | 400 | 80 | 0.05 |
| `analyze_sentiment` | 0.18 | 1000 | 200 | 0.25 |
| `get_csat_summary` | 0.22 | 1200 | 250 | 0.15 |

#### Research Agent Tools

| Tool | Failure Rate | Latency mean (ms) | Latency std (ms) | Low-confidence rate |
|---|---|---|---|---|
| `query_data` | 0.20 | 1800 | 400 | 0.15 |
| `analyze_trends` | 0.18 | 2200 | 500 | 0.20 |
| `generate_report` | 0.15 | 2000 | 400 | 0.25 |
| `compare_segments` | 0.22 | 2500 | 500 | 0.20 |
| `detect_churn_signals` | 0.25 | 2800 | 600 | 0.30 |

### Seed Control

```python
# Deterministic (debugging, unit tests)
simulator = MockSimulator(seed=42)

# Random (evaluation trials — each trial gets a different seed)
simulator = MockSimulator(seed=None)   # uses random.randint(0, 9999)
```

Seed is logged to MLflow per trial so any run can be reproduced.

### Output Format

Every tool returns a dict:

```python
{
    "result": "...",          # the actual output string
    "confidence": "high" | "medium" | "low",
    "simulated_latency_ms": 823.4,
    "tool_name": "search_leads",
    "success": True
}
```

On simulated failure, the tool raises `ToolExecutionError(tool_name, reason)` — which the recovery classifier catches and classifies as `FailureType.TOOL_ERROR`.

---

## 6. Evaluation Protocol — Full Specification

### What Is Being Measured

ABOS (adaptive planner + performance-based scheduler) vs. Static Baseline (same agents, fixed routing, no scheduler adaptation).

**The only variable between ABOS and baseline is the routing policy.**
Everything else — agents, tools, tool variance, recovery module — is identical.

### Metrics

| Metric | Formula | Unit |
|---|---|---|
| Task Completion Rate (TCR) | completed_steps / total_steps | % |
| Routing Accuracy (RA) | steps_with_correct_routing / steps_with_feedback | % |
| Recovery Success Rate (RSR) | recovered_steps / total_failed_steps | % |
| Average Step Latency | mean(execution.latency_ms) per scenario | ms |
| Scheduler Score Correlation | Pearson r(scheduler_score, step_success) | -1 to 1 |

Primary metrics for the paper: **TCR and RA.**
Secondary: RSR, latency, score correlation.

### Test Scenarios (9 total, locked)

#### Sales (3 scenarios)

| ID | Name | Goal Description |
|---|---|---|
| S1 | Q4 Cold Lead Outreach | Identify enterprise leads with no activity in 90 days, draft personalized outreach, update CRM with sent status |
| S2 | Pipeline Health Review | Analyze current pipeline for at-risk deals, qualify top 5 opportunities, generate a priority action list |
| S3 | Win/Loss Analysis | Compare closed-won vs closed-lost deals in last quarter, identify top 3 loss reasons, recommend strategy adjustments |

#### Support (3 scenarios)

| ID | Name | Goal Description |
|---|---|---|
| P1 | Ticket Backlog Triage | Triage 50 open tickets by priority, draft responses for top 10 high-priority items, flag escalations |
| P2 | CSAT Improvement Plan | Analyze last month's low-rated tickets, identify recurring complaint themes, draft improvement recommendations |
| P3 | Escalation Review | Review all escalated tickets from last 2 weeks, classify by root cause, draft resolution summaries |

#### Research (3 scenarios)

| ID | Name | Goal Description |
|---|---|---|
| R1 | Monthly KPI Report | Query all key business metrics for last 30 days, identify trends, generate executive summary report |
| R2 | Churn Risk Analysis | Detect customers showing churn signals in last 30 days, compare against retained segment, output risk-scored list |
| R3 | Segment Comparison | Compare enterprise vs SMB customer segments on engagement and revenue metrics, identify key differentiators |

### Trial Design

| Parameter | Value | Rationale |
|---|---|---|
| Trials per scenario | 7 | Odd number, sufficient for Wilcoxon, manageable runtime |
| Total runs (ABOS) | 63 (9 × 7) | |
| Total runs (Baseline) | 63 (9 × 7) | |
| Seed per trial | Random, logged | Reproducible but varied |
| Statistical test | Wilcoxon signed-rank | Non-parametric, paired, appropriate for small N |
| Significance threshold | p < 0.05 | Standard |
| Reporting format | mean ± std | Per scenario and aggregate |

### MLflow Logging (per trial)

Every trial logs:
```
run_name:       "{scenario_id}_{system}_{trial_number}"   e.g. "S1_ABOS_trial_3"
params:
  scenario_id, system (abos/baseline), trial_number, seed,
  scheduler_weights (W_sr, W_lat, W_conf), window_size, active_llm
metrics:
  tcr, routing_accuracy, rsr, avg_latency_ms, score_correlation
tags:
  department, scenario_name, system
artifacts:
  workflow_plan.json, step_outputs.json, execution_log.txt
```

---

## 7. Baseline — Written Contract

### What the Baseline Is

The baseline is a **static-workflow system** that uses the same agents, tools, and recovery module as ABOS, but with a **fixed routing policy** instead of the performance-based scheduler.

### Fixed Routing Policy

Tasks are routed by **department keyword matching** in a fixed priority order:

```
if step.assigned_department == "sales"    → always route to sales_agent
if step.assigned_department == "support"  → always route to support_agent
if step.assigned_department == "research" → always route to research_agent
```

Department assignment comes from the same planner LLM call as ABOS. The planner output is identical. The only difference: baseline ignores scheduler scores and always picks the single agent for that department.

### What Is Identical Between ABOS and Baseline

| Component | ABOS | Baseline | Same? |
|---|---|---|---|
| LLM used | configurable | same | ✅ |
| Planner node | ✅ | ✅ | ✅ |
| Department agents | sales, support, research | same | ✅ |
| Tool implementations | stochastic simulator | same simulator, same seeds | ✅ |
| Recovery module | ✅ | ✅ | ✅ |
| Memory retrieval | ✅ | ❌ disabled | ❌ intentional |
| Scheduler | performance-based scoring | fixed (always pick dept agent) | ❌ intentional |
| Profile updates | ✅ | ❌ no profile tracking | ❌ intentional |

Memory is disabled in baseline because it's part of the ABOS system, not an independent variable. This is documented in the paper as: "the baseline reflects a system with no adaptive components — fixed routing and no memory — equivalent to a manually-designed workflow pipeline."

### Baseline Does NOT

- Track agent performance over time
- Update confidence scores
- Retrieve past feedback
- Make any routing decision based on history

---

## 8. Department Agents — Capability Boundaries

Each agent handles exactly the task types listed. The planner is instructed to respect these boundaries.

### Sales Agent (`sales_agent`)

Handles: lead search, outreach drafting, CRM updates, pipeline analysis, deal qualification.
Does NOT handle: customer complaints, data analysis, market research.

### Support Agent (`support_agent`)

Handles: ticket triage, response drafting, escalation, sentiment analysis, CSAT analysis.
Does NOT handle: lead generation, revenue analysis, market research.

### Research Agent (`research_agent`)

Handles: data queries, trend analysis, report generation, segment comparison, churn detection.
Does NOT handle: CRM writes, customer responses, outreach drafting.

---

## 9. API Contract

Base URL: `/api/v1`
Auth: Bearer JWT on all endpoints except `/auth/register` and `/auth/login`

### Goal Submission (primary write path)

```
POST /goals/
Body: {
  title: string (3-200 chars)
  description: string (10-2000 chars)   ← this is the business goal
  priority: "low" | "medium" | "high" | "critical"
  target_departments: string[] | null   ← hint only, planner may override
  context: object | null                ← optional structured context
}
Response 202: GoalResponse (id, status="pending")
Side effect: execute_goal_task queued to Celery
```

### Feedback Submission (Level-2 memory write path)

```
POST /feedback/
Body: {
  execution_id: UUID
  rating: "correct" | "incorrect" | "partial"
  correction: string | null       ← free-text correction
  suggested_agent: string | null  ← routing correction
}
Response 201: FeedbackResponse
Side effects:
  - update_agent_profile_task queued
  - store_feedback_embedding_task queued (if correction text present)
```

### Goal Status Values

```
pending         → received, queued
planning        → planner running
ready           → workflow generated, awaiting execution (not currently used)
executing       → executor running
completed       → all steps completed
failed          → all steps failed or planner failed
cancelled       → manually cancelled
```

---

## 10. Database Schema Decisions

### Why pgvector for memory, not a separate vector DB

- Fewer moving parts — one DB to run, one DB to back up
- pgvector with IVFFlat index is sufficient for the scale of this project (hundreds, not millions of embeddings)
- Neon (cloud PostgreSQL) supports pgvector natively — zero additional config for cloud deployment

### Embedding Dimension: 1536

Matches OpenAI `text-embedding-3-small` and is compatible with Gemini embeddings (padded/truncated to 1536).
Stored in `feedback.embedding` as `Vector(1536)`.

### Soft vs Hard Deletes

All deletes are hard deletes (actual row removal). Soft deletes add complexity with no benefit at this project scale.

### JSON columns

`goals.context`, `goals.target_departments`, `workflow_steps.input_data`, `workflow_steps.output_data`, `executions.input_data`, `executions.output_data` — all stored as PostgreSQL JSON. No separate normalization needed at this scale.

---

## 11. Token Cost Logging (not scoring)

Add `token_cost: Optional[float]` to the `Execution` model. Log it per execution via LiteLLM's response usage fields:

```python
response.usage.prompt_tokens + response.usage.completion_tokens
# multiply by per-token cost for the active model
```

This data is collected for future analysis and paper limitations section.
**It does not affect routing decisions in v1.**

---

## 12. What Goes in the Paper vs What Doesn't

### In the paper

- Planner architecture and prompt design
- Scheduler scoring formula and weight justification
- Evaluation results: TCR, RA, RSR across 9 scenarios × 7 trials
- Ablation: no scheduler (random routing), no memory, no recovery
- Comparison against static baseline
- Positioning against Autonoma, Agentic ERP, MetaAgent-X

### Not in the paper (implementation detail only)

- Full FastAPI route implementation
- Frontend dashboard
- Docker setup
- Celery worker configuration
- Tool implementations (described briefly as "realistic mock implementations with controlled stochastic variance")

### What must be cited, never claimed

- Self-Healing Orchestrators (2026) — recovery module
- Governance by Design (2026) — Level-2 memory model
- Autonoma (2026) — baseline comparison point
- APM Manifesto (2026) — conceptual foundation

---

## 13. Build Order (locked)

### Phase 1 — Runnable (current sprint)

| Step | Deliverable | Status |
|---|---|---|
| 1 | Docker (local + cloud) | 🔲 |
| 2 | First Alembic migration | 🔲 |
| 3 | Mock tools with controlled variance (this spec, Section 5) | 🔲 |
| 4 | `scripts/run_agent_debug.py` | 🔲 |

### Phase 2 — Evaluable

| Step | Deliverable | Status |
|---|---|---|
| 5 | Baseline implementation (from Section 7 spec) | 🔲 |
| 6 | Evaluation runner — N-trial design (Section 6) | 🔲 |
| 7 | Unit tests — scheduler, planner, classifier | 🔲 |
| 8 | MLflow integration in eval runner | 🔲 |

### Phase 3 — Demonstrable

| Step | Deliverable | Status |
|---|---|---|
| 9 | Frontend `src/` | 🔲 |
| 10 | Docker cloud compose | 🔲 |

### Update this table as steps complete — change 🔲 to ✅ with date.

---

## 14. Decisions That Are Locked (do not reopen)

| Decision | What was decided | Why locked |
|---|---|---|
| Number of departments | 3 (Sales, Support, Research) | Validated against literature — 8 is unbuildable |
| Scheduler type | Heuristic, non-RL | RL requires training infrastructure out of scope |
| Scheduler signals | success_rate + latency + confidence | Specified in proposal, no token cost in v1 |
| Scheduler weights | 0.5 / 0.2 / 0.3 | Locked for evaluation — change requires re-running all trials |
| Trials per scenario | 7 | Sufficient for Wilcoxon, manageable runtime |
| Novel contributions | Planner + Scheduler only | Validated report confirmed all others are closed gaps |
| Recovery module source | Self-Healing Orchestrators (2026) | Adopted with citation — not our contribution |
| Memory model | Governance-by-Design Level-2 | Adopted with citation — not our contribution |
| Embedding dimension | 1536 | Compatible with both Gemini and OpenAI embeddings |
| Statistical test | Wilcoxon signed-rank | Non-parametric, appropriate for N=7 paired samples |

---

## 15. Open Questions (need team decision)

| Question | Options | Deadline |
|---|---|---|
| Which LLM for evaluation runs? | Gemini 1.5 Pro vs GPT-4o | Before Phase 2 starts |
| Cloud hosting platform | Railway vs Render vs AWS | Before Phase 3 starts |
| Ablation study depth | 4 ablations (no scheduler, no memory, no recovery, static workflow) vs 2 (no scheduler, no memory) | Before eval runner is written |
| Frontend owner | Who builds `src/`? | Assign now |
| Evaluation runner owner | Who owns `evaluation/` scripts? | Assign now |
