# ABOS Agent System — Developer Guide

This document explains how the LangGraph-based agent system works, how to extend it, and what each component is responsible for.

---

## Overview

```
backend/agents/
├── state.py          ← Shared graph state (read this first)
├── graph.py          ← LangGraph graph: nodes + edges
├── planner/
│   ├── planner.py    ← Goal-to-workflow decomposition (LLM call)
│   └── prompts.py    ← Planner prompt templates
├── scheduler/
│   ├── scheduler.py  ← Performance-based routing logic
│   └── scoring.py    ← Score formula: success_rate, latency, confidence
├── department/
│   ├── base.py       ← Base class all department agents inherit from
│   ├── sales.py      ← Sales department agent
│   ├── support.py    ← Customer Support department agent
│   └── research.py   ← Research & Analytics department agent
├── memory/
│   ├── memory.py     ← Level-2 explicit-feedback memory layer
│   └── embeddings.py ← LiteLLM embedding calls for pgvector
└── recovery/
    ├── recovery.py   ← Failure detection + bounded retry logic
    └── classifier.py ← Failure type classification
```

---

## 1. State (`state.py`)

**Read this first before touching anything else.**

`ABOSState` is the single TypedDict that gets passed between every node in the graph. Think of it as the "job sheet" that travels through the pipeline.

```python
class ABOSState(TypedDict):
    goal_id: str
    goal_description: str
    workflow_plan: List[WorkflowStepState]   # set by planner
    current_step_index: int                  # incremented by executor
    completed_steps: List[WorkflowStepState] # appended by each step
    failed_steps: List[WorkflowStepState]
    retrieved_memory: List[dict]             # injected by memory node
    recovery_attempts: int
    final_status: str
    logs: List[str]
    # ... (see state.py for full definition)
```

**Rules:**
- Nodes only read fields they need and write fields they own
- Never mutate state directly — return a partial dict with only the fields you changed
- `completed_steps` and `failed_steps` use `operator.add` — LangGraph automatically merges them

---

## 2. Graph (`graph.py`)

The LangGraph `StateGraph` defines the flow:

```
START
  │
  ▼
memory_retrieval          ← fetch similar past feedback from pgvector
  │
  ▼
planner                   ← LLM decomposes goal into workflow steps
  │
  ▼
scheduler                 ← score agents, assign each step to best agent
  │
  ▼
executor                  ← run current step via assigned department agent
  │
  ├── success ────────────► increment step → back to executor (next step)
  │                                       → summarizer (if last step)
  │
  └── failure ────────────► recovery
                              │
                              ├── recovered ──► executor (retry)
                              └── max retries ► mark failed → next step
  │
  ▼
summarizer                ← LLM generates a summary of the completed run
  │
  ▼
END
```

Edges use conditional routing — `should_continue()` checks `current_step_index` vs `len(workflow_plan)`.

---

## 3. Planner (`planner/`)

**Research contribution #1 — Goal-to-Workflow Generation**

The planner takes the raw business goal and calls the LLM to produce a structured `List[WorkflowStepState]`.

### What it does

1. Retrieves semantically similar past feedback from the memory layer (injected into prompt)
2. Calls LiteLLM with a structured output prompt
3. The LLM returns a JSON list of steps — each step has a department hint, title, description, and input data
4. Steps are validated against `WorkflowStepState` using Pydantic

### Key file: `planner/prompts.py`

This is where the prompt templates live. If results are poor, **this is where to iterate first**.

The system prompt instructs the LLM to:
- Output only valid JSON (no markdown, no explanation)
- Respect the 3-department constraint (sales / support / research)
- Use past feedback corrections to avoid known bad routings

### Extending the planner

To add a new department:
1. Add the department name to `VALID_DEPARTMENTS` in `planner.py`
2. Add a description of what that department handles to the system prompt in `prompts.py`
3. Create the department agent in `department/`
4. Register it in `graph.py`

---

## 4. Scheduler (`scheduler/`)

**Research contribution #2 — Interpretable Performance-Based Scheduling**

The scheduler scores each available agent for a given step and picks the highest scorer.

### Scoring formula

```python
score = (
    WEIGHT_SUCCESS_RATE * agent.success_rate
    + WEIGHT_LATENCY    * latency_score(agent.avg_latency_ms)
    + WEIGHT_CONFIDENCE * agent.confidence_score
)
```

Where:
- `success_rate` — fraction of successful executions in the last N (window_size) runs
- `latency_score` — normalized inverse latency: `1 / (1 + avg_latency_ms / 1000)`
- `confidence_score` — composite score persisted in `agent_profiles` table, updated after each feedback

Default weights (adjustable in `config.py`):
```
WEIGHT_SUCCESS_RATE = 0.5
WEIGHT_LATENCY      = 0.2
WEIGHT_CONFIDENCE   = 0.3
```

### Why not RL?

MetaAgent-X uses end-to-end RL with GRPO and hierarchical rollouts. That requires GPU training infrastructure and is out of scope for this project. Our heuristic scheduler is:
- Interpretable (you can explain every routing decision)
- Updatable in real-time (no retraining)
- Evaluable within the project timeline

This is a **deliberate design choice documented in the proposal** — not a shortcut.

### Updating scores

After each execution, `tasks.py` calls `scoring.py` to recompute and persist the agent's scores.
After each feedback entry, `feedback_service.py` triggers a score update via Celery.

---

## 5. Department Agents (`department/`)

Each agent inherits from `BaseDepartmentAgent` and implements its own tool set.

### Base class interface

```python
class BaseDepartmentAgent:
    name: str
    department: str
    tools: List[BaseTool]

    async def execute(self, step: WorkflowStepState, context: dict) -> dict:
        """Run the step. Returns output_data dict."""
        ...
```

### Sales Agent (`sales.py`)

Handles: lead generation, CRM updates, outreach campaigns, pipeline tracking.

Tools:
- `search_leads` — search/filter leads by criteria
- `draft_outreach` — LLM-drafted personalized outreach message
- `update_crm` — write outcome back to CRM record
- `analyze_pipeline` — summarize pipeline health

### Support Agent (`support.py`)

Handles: ticket triage, response drafting, escalation, satisfaction analysis.

Tools:
- `triage_ticket` — classify ticket type and priority
- `draft_response` — LLM-drafted customer response
- `escalate` — flag for human review
- `analyze_sentiment` — sentiment analysis on customer messages

### Research Agent (`research.py`)

Handles: data queries, trend analysis, report generation, market research.

Tools:
- `query_data` — structured data query
- `analyze_trends` — identify trends in provided data
- `generate_report` — LLM-generated summary report
- `compare_segments` — compare two customer/product segments

### Adding a new tool to an agent

```python
from langchain_core.tools import tool

@tool
def my_new_tool(input: str) -> str:
    """Describe what this tool does — the LLM reads this description."""
    # implementation
    return result

# Then add to the agent's tools list:
class SalesAgent(BaseDepartmentAgent):
    tools = [search_leads, draft_outreach, update_crm, analyze_pipeline, my_new_tool]
```

---

## 6. Memory Layer (`memory/`)

**Level-2 Explicit-Feedback Memory (Governance-by-Design maturity model)**

> Note: The memory *framework* (the 3-level maturity model) already exists in the literature.
> ABOS's contribution is implementing Level-2 for adaptive workflow planning specifically.
> Do not claim the framework itself as novel in any writeup.

### How it works

**Write path** (after execution):
1. User submits feedback via `POST /api/v1/feedback`
2. `FeedbackService.create()` stores the feedback in PostgreSQL
3. Celery task `update_agent_profile_task` runs asynchronously
4. If a correction text was provided, `embeddings.py` calls LiteLLM to embed it
5. The 1536-dim embedding is stored in the `feedback.embedding` pgvector column

**Read path** (before planning):
1. `memory_retrieval` node runs before the planner
2. Embeds the current goal description
3. Runs a pgvector similarity search: `SELECT ... ORDER BY embedding <=> $1 LIMIT 5`
4. Returns the top-5 most similar past feedback entries
5. These are injected into the planner prompt as "past corrections"

### pgvector queries

```sql
-- Find similar feedback (cosine distance)
SELECT correction, suggested_agent, rating
FROM feedback
WHERE embedding IS NOT NULL
ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 5;
```

The `<=>` operator is cosine distance. Use `<->` for L2 distance if needed.

---

## 7. Recovery Module (`recovery/`)

> **This module is adopted from Self-Healing Agentic Orchestrators (2026) with citation.**
> Do NOT claim it as a novel contribution in any writeup or presentation.

### What it does

When an agent step fails, the recovery module:
1. **Classifies** the failure type (timeout, LLM error, tool error, invalid output)
2. **Decides** whether to retry, reroute, or skip
3. **Applies** a bounded retry budget (`max_recovery_attempts` in state)
4. **Logs** the recovery attempt for evaluation

### Failure types

| Type | Action |
|---|---|
| `timeout` | Retry with increased timeout |
| `llm_error` | Retry (transient) |
| `tool_error` | Reroute to different agent if available |
| `invalid_output` | Retry with corrected prompt |
| `max_retries` | Mark step as failed, continue |

### Recovery budget

Configured via `AGENT_MAX_RETRIES` in `.env` (default: 3). The graph checks `recovery_attempts >= max_recovery_attempts` and skips to the next step if exceeded.

---

## 8. LLM Calls via LiteLLM

All LLM calls go through LiteLLM. This means switching providers is a one-line config change.

```python
from litellm import acompletion

response = await acompletion(
    model=settings.ACTIVE_LLM,     # e.g. "gemini/gemini-1.5-pro"
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ],
    response_format={"type": "json_object"},  # structured output
    temperature=0.2,
)
```

To switch to OpenAI:
```bash
# In .env:
ACTIVE_LLM=openai/gpt-4o
OPENAI_API_KEY=your-key
```

No code changes needed.

---

## 9. Running Just the Agent System (for debugging)

You can invoke the graph directly without going through the full API/Celery stack:

```python
# scripts/run_agent_debug.py
import asyncio
from backend.agents.graph import build_graph

async def main():
    graph = build_graph()
    result = await graph.ainvoke({
        "goal_id": "test-001",
        "workflow_id": "wf-001",
        "user_id": "user-001",
        "goal_title": "Q4 Enterprise Outreach",
        "goal_description": "Identify and contact 20 high-value enterprise leads that have gone cold in the past 90 days.",
        "goal_priority": "high",
        "goal_context": {},
        "target_departments": None,
        "current_step_index": 0,
        "completed_steps": [],
        "failed_steps": [],
        "retrieved_memory": [],
        "recovery_attempts": 0,
        "max_recovery_attempts": 3,
        "logs": [],
    })
    print(result["final_status"])
    print(result["summary"])

asyncio.run(main())
```

```bash
poetry run python scripts/run_agent_debug.py
```

---

## 10. Evaluation

The evaluation protocol compares ABOS against a **static-workflow baseline** (fixed routing, no scheduler adaptation).

Metrics reported:
- **Task completion rate** — % of steps completed successfully
- **Routing accuracy** — % of steps routed to the department that feedback confirms was correct
- **Recovery success rate** — % of failed steps recovered vs total failures

Evaluation scripts live in `evaluation/` and `tests/evaluation/`. All runs are logged to MLflow.

See `docs/EVALUATION.md` for the full evaluation setup.

---

## Quick Reference

| I want to... | Where to look |
|---|---|
| Change how goals are decomposed | `agents/planner/prompts.py` |
| Change scheduler weights | `agents/scheduler/scoring.py` |
| Add a tool to an agent | `agents/department/sales.py` (or support/research) |
| Change memory retrieval (top-K, similarity threshold) | `agents/memory/memory.py` |
| Change retry/recovery logic | `agents/recovery/recovery.py` |
| Change the graph flow | `agents/graph.py` |
| Add a new API endpoint | `api/v1/routes/`, `schemas/`, `services/` |
| Add a new DB table | `db/models/`, then run `alembic revision --autogenerate` |
| Run experiments | `evaluation/`, log to MLflow |
