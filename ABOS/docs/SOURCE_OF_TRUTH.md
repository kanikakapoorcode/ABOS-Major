# ABOS — Implementation Source of Truth

> This is the single authoritative document for all implementation decisions.
> If code contradicts this document, the code is wrong.
> If you want to change something here, discuss with the team first, then update this file, then update the code.
>
> Last updated: November 25, 2026 (synced shared-plan eval controls, quick-commerce tool spec, workflow multilingual persistence, API contract, and build status)

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

### First Case Study: Sheetal's Cosmetics Business (Pre-launch)

The primary case is a prospective owner deciding how to enter a local market with many similar cosmetics shops. A post-launch stock/replenishment review is a later use case, not the primary case for this research question.

- Input: a Hindi or English spoken goal, location or PIN code, service radius, startup budget, and intended customer segment. ABOS asks for missing essentials one at a time.
- Evidence: competitor locations and observed product/price ranges; local customer needs or survey results; online demand/availability signals; and supplier prices, minimum order quantities, and authenticity information. Each observation must retain its source and date.
- Workflow: validate evidence coverage, map competitors, compare local assortment with customer and online signals, identify possible gaps, check supplier and margin feasibility, then present a budget-aware starter assortment and differentiation plan for Sheetal's review.
- Safety and data rules: never claim a product is absent based only on a shop listing; distinguish missing evidence from evidence of absence; do not treat search popularity alone as purchase demand; disclose unavailable cost/supplier information; never place orders.
- Voice is the accessibility channel, not a novelty claim by itself. Any claim that this differentiates ABOS from existing products requires a separate literature and product comparison.

#### Voice Implementation Requirements

The voice interaction path is not yet implemented. Build it as a thin frontend-to-backend vertical slice rather than completing either side in isolation:

1. Define the interaction and API contract: audio input returns a transcript and recognized language; expose provider confidence only when available, and do not treat it as calibrated certainty.
2. Build the minimum UI: microphone start/stop, recording playback, editable transcript, clear permission/transcription errors, and typed-input fallback.
3. Add a backend speech-to-text adapter. Select a provider only after testing Hindi, English, code-switching, relevant names, accents, and noisy recordings.
4. Track each critical extracted detail (such as goal, location, and budget) as unconfirmed, user-corrected, or confirmed. Ask one clarification at a time; do not pass an unconfirmed critical detail to the planner.
5. Apply corrections within the current conversation. Persist personal vocabulary or speech preferences only with explicit consent and provide a way to delete them. Do not infer or persist an accent profile automatically.
6. Before calling the voice experience accessible for low-literacy users, add speech output for readbacks and answers, with replay and a language/speed choice.
7. Keep recordings ephemeral by default. Any retention for debugging or improvement requires explicit consent and a defined retention/deletion policy.

The first experimental milestone is recording → transcription → user review/correction → confirmation of critical details. TTS, persistent personalization, and full business-workflow integration follow after this slice is tested end to end.

Evaluate the two research contributions separately:

1. **Planner:** compare the generated workflow with a reviewed, fixed reference plan using the same goal and evidence.
2. **Scheduler:** give adaptive and fixed routing the same plan, evidence, agents, and memory condition; change only the routing policy.

Measure workflow step adherence, supported versus unsupported claims, product-gap precision/recall against a manually reviewed local-market reference, feasibility under budget, and end-to-end latency. Measure voice usability separately. For the 9 synthetic paired scenarios, `evaluation/run_evaluation.py` now generates one shared frozen plan per trial, injects it into both ABOS and the baseline, and mirrors the `language`, `compliance_plan`, and `compliance_output` nodes in `evaluation/baseline.py` (with memory disabled in the baseline via `noop_memory_node`). However, until controlled real-market evidence collection, manual reference sets, and real tool execution replace `MockSimulator`, results are exploratory for the Sheetal local-market claims.

### What Is Adopted (cite, never claim)

| Component | Source | Citation |
|---|---|---|
| Failure recovery | Self-Healing Agentic Orchestrators (2026) | arxiv 2606.01416 |
| Memory maturity model | Governance by Design (2026) | arxiv 2605.20210 |

---

## 2. System Architecture

### Component Map

```
User Goal (natural language,any language)
        │
        ▼
  FastAPI  ──► Celery Task Queue (Redis)
                        │
                        ▼
              LangGraph Graph
              ┌──────────────────────────────────────────┐
              │                                          │
              │  language          [multilingual input]  │
              │       ↓                                  │
              │  memory_retrieval                        │
              │       ↓                                  │
              │   planner          [Contribution 1]      │
              │       ↓                                  │
              │  compliance_plan   [safety gate]         │
              │       ↓ approved / ──blocked──► END      │
              │  scheduler         [Contribution 2]      │
              │       ↓                                  │
              │  executor ──► department agent           │
              │       ↓ success                          │
              │ compliance_output [per-step safety]     │
              │       ↓ safe → next / summary           │
              │       ↓ blocked → summary               │
              │ executor failure → recovery (adopted)   │
              │       ↓                                  │
              │  summarizer  [localises output]          │
              └──────────────────────────────────────────┘
                        │
                        ▼
              PostgreSQL + pgvector
```

### Data Flow (one goal, end to end)

```
1. POST /api/v1/goals/          → goal created, status=pending
2. Celery: execute_goal_task    → status=planning
3. language node                → detect input language; translate title+description to English if needed
4. memory_retrieval node        → embed goal, fetch top-5 similar feedback
5. planner node                 → LLM decomposes goal into WorkflowStepState list
6. compliance_plan node         → LLM reviews full plan for regulatory/legal risk before execution
                                   high/critical risk → plan blocked, final_status=compliance_blocked
                                   low/medium risk    → advisory flags stored, execution proceeds
7. scheduler node               → score agents per step, assign best
8. executor node (loop)         → run each step via department agent
9. compliance_output node       → LLM reviews each step output before passing forward
                                   unsafe output → step marked compliance_failed; later steps do not run
10. recovery node (on failure)  → classify → retry/reroute/skip
                                   executor failures → recovery for the current step
11. summarizer node             → LLM summary of run; translate summary+flags to user's language
12. DB write                     → workflow status, summary, localised_summary, detected_language, compliance_flags, localised_compliance_flags, step outcomes, execution records
13. feedback (async)            → user corrects routing → profile update → embedding store
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
| `goal_title` | str | input | May be overwritten by language_node with English translation |
| `goal_description` | str | input | May be overwritten by language_node with English translation |
| `goal_priority` | str | input | Immutable |
| `goal_context` | dict | input | Immutable |
| `target_departments` | list | input | Hint only, planner may override |
| `detected_language` | str | language_node | BCP-47 tag of user's input language (e.g. "hi", "mr", "en") |
| `original_goal_title` | str | language_node | Unmodified user-submitted title, preserved for audit and output localisation |
| `original_goal_description` | str | language_node | Unmodified user-submitted description, preserved for audit and output localisation |
| `workflow_plan` | List[WorkflowStepState] | planner → scheduler → executor | Each node may update steps in-place |
| `current_step_index` | int | executor / recovery | Incremented on success or skip |
| `completed_steps` | List[WorkflowStepState] | executor (operator.add) | Append-only |
| `failed_steps` | List[WorkflowStepState] | recovery (operator.add) | Append-only |
| `retrieved_memory` | list | memory_retrieval | Read by planner only |
| `recovery_attempts` | int | recovery | Reset to 0 when a new step starts |
| `max_recovery_attempts` | int | input | Default: 3 |
| `compliance_plan_result` | dict | compliance_plan_node | Full LLM compliance review of the workflow plan |
| `compliance_flags` | List[str] | compliance_plan_node / compliance_output_node (operator.add) | Accumulated flags from plan-level and per-step output checks |
| `final_status` | str | summarizer | completed / failed / partially_completed / compliance_blocked |
| `summary` | str | summarizer | LLM-generated run summary in English |
| `localised_summary` | str | summarizer | Summary translated to user's detected language (same as summary if English) |
| `localised_compliance_flags` | List[str] | summarizer (operator.add) | Compliance flags translated to user's detected language |
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
| `task_type` | str | planner | Canonical task type from closed taxonomy (e.g. lead_search, ticket_triage, quick_commerce_analysis) |
| `input_data` | dict | planner | Parameters for the agent |
| `output_data` | dict | executor | Agent's output |
| `status` | str | executor / recovery | pending / running / completed / failed / retrying / skipped / compliance_failed |
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

### Evidence Hierarchy & Task-Conditioned Performance

To maximize routing precision without fragmenting empirical data, the scheduler evaluates historical evidence according to a strict **3-tier sufficiency-aware hierarchy**:

```text
               Routing Request (department, task_type)
                                │
                                ▼
                     task_type in canonical set?
                       ↙                   ↘
                     YES                    NO (or None)
                      ↓                          ↓
        AgentTaskProfile in DB?                  │
              ↙        ↘                         │
            YES         NO                       │
             ↓           │                       │
      total_executions   │                       │
       >= MIN_TASK (3)   │                       │
         ↙        ↘      │                       │
       YES         NO    │                       │
        ↓           └────┼───────────────────────┘
  [Tier 1: Task Profile]  ▼
                  AgentProfile in DB?
                        ↙       ↘
                      YES        NO
                       ↓          │
                total_executions  │
                     >= 1         │
                   ↙        ↘     │
                 YES         NO   │
                  ↓           └───┘
          [Tier 2: Aggregate]     ▼
                        [Tier 3: Cold-Start Prior (0.41)]
```

#### Canonical Task Taxonomy (Code-Enforced, Closed Set)
- **Sales**: `lead_search`, `outreach_drafting`, `crm_update`, `pipeline_analysis`, `deal_qualification`
- **Support**: `ticket_triage`, `response_drafting`, `ticket_escalation`, `sentiment_analysis`, `csat_analysis`
- **Research**: `data_query`, `trend_analysis`, `report_generation`, `segment_comparison`, `churn_detection`, `quick_commerce_analysis`


Unrecognized or free-text task strings are strictly treated as `None` (no guessing or fuzzing), falling back safely to Tier-2 aggregate profiles.

### Cold Start Priors (agent has no history)

```text
success_rate     = 0.5   (neutral — no evidence either way)
avg_latency_ms   = 0.0   → latency_score = 0.5 (neutral fallback for missing/invalid data, never 1.0)
confidence_score = 0.2   (low prior confidence — unproven agent)
composite_score  = 0.41  (0.50*0.5 + 0.20*0.5 + 0.30*0.2 = 0.41)
```

This establishes an honest cold-start prior representing "no empirical evidence yet". As actual executions occur, performance metrics ($SR$, Latency, Confidence) emerge dynamically from real runs and performance-based routing takes over.

### Cold-Start Tie-Breaking & Primary Candidate Selection
When candidates have identical cold-start priors (0.41), the scheduler deterministically routes to the primary candidate (first candidate registered per department) and records `uncertainty = True`. Secondary candidates accumulate execution history through evaluation trials or explicit candidate benchmarking. This deterministic selection policy is explicitly documented as a non-RL architectural trade-off.

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
| `quick_commerce_trend` | 0.20 | 2400 | 500 | 0.15 |

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

ABOS (Goal-to-Workflow Planner + Performance-Based Scheduler) vs. Static Baseline (Same Goal-to-Workflow Planner + Fixed Routing Policy).

**The sole independent variable is the routing policy.**
Everything else — LLM model, prompt decomposition, memory conditions, candidate agents, tool simulator seeds, recovery module — is strictly identical.

### Metrics

| Metric | Formula / Source | Unit |
|---|---|---|
| Task Completion Rate (TCR) | `completed_steps / total_steps` | % |
| Ground-Truth Routing Accuracy (RA) | Evaluated post-hoc against the **Simulator Oracle** (`ORACLE_OPTIMAL_ROUTING`) | % |
| Recovery Success Rate (RSR) | `recovered_steps / (failed_steps + recovered_steps)` (Returns `None` if 0 failures) | % |
| Average Step Latency | `sum(executed_step_latency) / count(executed_steps)` | ms |
| Total Scenario Latency | `sum(executed_step_latency)` | ms |
| Scheduler Score Correlation | Pearson $r(\text{scheduler\_score}, \text{step\_success})$ (Secondary diagnostic) | -1 to 1 |

Primary metrics for the paper: **TCR, Ground-Truth Routing Accuracy, and Average Step Latency.**
Secondary: RSR, Score Correlation.

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
if step.assigned_department == "sales"    → always route to sales_outreach_fast (or sales_agent alias)
if step.assigned_department == "support"  → always route to support_tier1_fast (or support_agent alias)
if step.assigned_department == "research" → always route to research_kpi_quick (or research_agent alias)
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

Handles: data queries, trend analysis, report generation, segment comparison, churn detection, quick-commerce trend analysis.
Does NOT handle: CRM writes, customer responses, outreach drafting.

---

## 9. API Contract

Base URL: `/api/v1` (plus `GET /health` at root)
Auth: Bearer JWT on all endpoints except `/auth/register`, `/auth/login`, `/auth/refresh`, and `/health`

### Additional Core Endpoints

- `GET /auth/me` → current authenticated `UserResponse` (`id`, `email`, `full_name`, `is_active`, `created_at`); `/auth/login` and `/auth/register` also return `user` inside `TokenResponse`
- `GET /workflows/?goal_id={uuid}` → filter user workflows by goal; `WorkflowResponse` includes `detected_language`, `summary`, `localised_summary`, `compliance_flags`, `localised_compliance_flags`, and `error`
- `POST /workflows/{workflow_id}/retry` → queues `execute_workflow_task` to re-run the workflow
- `GET /agents/` → Tier-2 aggregate `AgentProfile` list
- `GET /agents/task-profiles` → Tier-1 `AgentTaskProfile` list (optional `department`, `task_type` filters)

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
compliance_blocked → plan was reviewed and blocked before execution started
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
| 1 | Docker (local + cloud) | ✅ |
| 2 | Alembic migrations (`0001`, `0002`, `0003`) | ✅ |
| 3 | Mock tools with controlled variance (this spec, Section 5) | ✅ |
| 4 | `scripts/run_agent_debug.py` | ✅ |

### Phase 2 — Evaluable

| Step | Deliverable | Status |
|---|---|---|
| 5 | Baseline implementation (from Section 7 spec) | ✅ |
| 6 | Evaluation runner — N-trial design (Section 6) | ✅ |
| 7 | Unit tests — scheduler, planner, classifier, metrics | ✅ |
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
