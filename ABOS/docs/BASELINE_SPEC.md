# ABOS Baseline System — Written Specification

> This document is the authoritative contract for the static-workflow baseline
> used in all ABOS evaluation experiments.
>
> If a reviewer asks "are you sure the only difference between ABOS and the
> baseline is the routing policy?" — this document is the answer.
>
> Do NOT change baseline behaviour without updating this document first
> and discussing with the team. Any undocumented difference between ABOS
> and the baseline is a confound that invalidates the comparison.

---

## 1. Purpose

The baseline exists to isolate the contribution of ABOS's two novel components:

| Component | ABOS | Baseline |
|---|---|---|
| Goal-to-workflow planner | ✅ LLM decomposes goal | ✅ **identical** |
| Performance-based scheduler | ✅ weighted score routing | ❌ fixed routing |
| Level-2 memory retrieval | ✅ pgvector feedback lookup | ❌ **disabled** |
| Department agents | ✅ sales / support / research | ✅ **identical** |
| Tool implementations | ✅ MockSimulator variance | ✅ **identical same seed** |
| Recovery module | ✅ classify → retry/reroute | ✅ **identical** |
| Agent profile updates | ✅ after each execution | ❌ **disabled** |

The only controlled variables are:
1. **Routing policy** — adaptive score vs. fixed assignment
2. **Memory** — retrieved feedback injected into planner vs. not

Everything else is identical. Same LLM, same agents, same tools, same seed,
same recovery module, same evaluation scenarios.

---

## 2. Baseline Routing Policy (Fixed Assignment)

The baseline routes every workflow step to the single registered agent for
that step's department, with no scoring and no history.

```python
BASELINE_ROUTING = {
    "sales":    "sales_outreach_fast",       # Primary candidate (aliased as sales_agent)
    "support":  "support_tier1_fast",        # Primary candidate (aliased as support_agent)
    "research": "research_kpi_quick",        # Primary candidate (aliased as research_agent)
}

def baseline_route(department: str) -> str:
    return BASELINE_ROUTING.get(department, f"{department}_agent")
```

**No score is computed. No profile is loaded. No history is consulted.**

The `scheduler_score` field on each step is set to `None` in baseline runs,
making it trivially distinguishable from ABOS runs in the results DB.

---

## 3. What Is Disabled in the Baseline

### 3.1 Memory Retrieval
- The `memory_retrieval_node` is replaced with a no-op that returns
  `retrieved_memory = []`
- The planner receives no past feedback context
- Embeddings are not computed and not stored during baseline runs

**Rationale:** Memory retrieval is part of the ABOS system, not an
independent variable. Disabling it in the baseline means the comparison
isolates routing + memory together as the "ABOS adaptive system" vs.
the "static baseline."

### 3.2 Agent Profile Updates
- After each execution in a baseline run, `update_agent_profile_task`
  is NOT called
- Agent profiles in the DB are not modified during baseline runs
- This prevents baseline runs from contaminating ABOS profile data

**Implementation:** The baseline runner passes `update_profiles=False`
to the execution loop.

### 3.3 Feedback Embedding Storage
- Feedback submitted during baseline evaluation runs is not embedded
- No pgvector writes occur during baseline trials

---

## 4. What Is Identical Between ABOS and Baseline

### 4.1 The Planner
Exactly the same `planner_node` is called with exactly the same goal
description and priority. The only difference: no memory context is
injected (Section 3.1).

This means both ABOS and the baseline start from the same workflow plan
structure — the routing policy is the only variable affecting step
assignment.

### 4.2 Tool Implementations and MockSimulator
Both systems use the exact same `MockSimulator` instance with the
**same seed** for each paired trial.

This is critical: if trial N of ABOS uses seed=7341, then trial N of
the baseline also uses seed=7341. Same tools, same failure draws, same
latency samples. The only thing that differs is which agent the step
was routed to — which is always the same agent (one per department)
in the baseline.

```python
# In the evaluation runner — both systems share the same seed per trial
trial_seed = trial_seeds[trial_idx]
set_simulator(MockSimulator(seed=trial_seed))
abos_result   = await run_abos(scenario, trial_seed)
baseline_result = await run_baseline(scenario, trial_seed)
```

### 4.3 Recovery Module
Identical `recovery_node` runs in both systems. If a tool fails, the
same classify → retry/reroute/skip logic applies.

The only difference: baseline has no alternative agent to reroute to
(one agent per department), so `has_alternative_agent = False` always,
and `RecoveryAction.REROUTE` degrades to `RecoveryAction.SKIP`.

### 4.4 Max Recovery Attempts
Same value: `max_recovery_attempts = 3` (from `config.py`).

---

## 5. Baseline Graph Structure

The baseline uses a modified LangGraph graph where:

- `memory_retrieval` → replaced with `noop_memory_node`
- `scheduler` → replaced with `baseline_scheduler_node`
- All other nodes → identical to ABOS

```
START
  → noop_memory          (returns retrieved_memory=[])
  → planner              (identical LLM decomposition)
  → baseline_scheduler   (fixed dept → agent mapping, no scoring)
  → executor             (identical)
  → recovery             (identical, but reroute always degrades to skip)
  → summarizer           (identical)
END
```

---

## 6. Baseline Scheduler Node Implementation Contract

```python
async def baseline_scheduler_node(state: ABOSState) -> dict:
    """
    Fixed routing: assigns the single registered agent for each
    step's department. No scoring. No profile lookup. No DB access.
    scheduler_score is set to None on all steps.
    """
    plan = state.get("workflow_plan") or []
    scheduled = []
    for step in plan:
        updated = dict(step)
        updated["assigned_agent"] = BASELINE_ROUTING.get(
            step["assigned_department"],
            f"{step['assigned_department']}_agent"
        )
        updated["scheduler_score"] = None  # explicitly None for baseline
        scheduled.append(updated)
    return {
        "workflow_plan": scheduled,
        "logs": [f"Baseline scheduler: fixed routing for {len(scheduled)} steps."],
    }
```

---

## 7. Trial Pairing Protocol

For statistical validity, ABOS and baseline trials are **paired**:
each scenario is run N times, and trial i of ABOS is directly compared
to trial i of the baseline using the same seed.

```
Trial 1: seed=s1  →  ABOS(S1, s1)  vs  Baseline(S1, s1)
Trial 2: seed=s2  →  ABOS(S1, s2)  vs  Baseline(S1, s2)
...
Trial 7: seed=s7  →  ABOS(S1, s7)  vs  Baseline(S1, s7)
```

Seeds are generated once per experiment run and saved to MLflow as
a parameter so any trial can be reproduced exactly.

---

## 8. Expected Behaviour Differences

Given the SOURCE_OF_TRUTH §5 tool profiles:

| Metric | Expected direction | Reasoning |
|---|---|---|
| Task Completion Rate | ABOS ≥ Baseline | After enough trials, ABOS scheduler learns to avoid high-failure-rate tools/agents and routes around failures more effectively |
| Routing Accuracy | ABOS > Baseline | Baseline always picks the single available agent; ABOS adapts based on confidence |
| Recovery Success Rate | Similar early, ABOS better later | Both use same recovery module; ABOS benefits from reroute when multiple agents exist |
| Average Latency | ABOS ≤ Baseline | ABOS latency-weights routing; Baseline ignores latency |
| Scheduler Score Correlation | ABOS: positive r; Baseline: N/A | Baseline has no scores to correlate |

**Important:** These are expected directions, not guaranteed outcomes.
The evaluation will confirm or refute them. Do not adjust the baseline
spec to produce a particular result.

---

## 9. What the Comparison Proves (and Does Not Prove)

### Proves
- Whether adaptive scheduling (performance-based) produces better task
  completion and routing accuracy than fixed assignment, given the same
  agents, tools, and recovery logic
- Whether the memory layer (past feedback injection) contributes to
  planner quality over time

### Does Not Prove
- That ABOS is better than all possible baselines (only this one)
- That the tool implementations are production-ready
- That the LLM always produces valid workflow plans
- That the scheduler would generalise to more than 3 departments

These limitations are documented in the paper's limitations section.

---

## 10. File Locations

| File | Purpose |
|---|---|
| `evaluation/baseline.py` | Baseline graph builder and runner |
| `evaluation/run_evaluation.py` | Paired trial runner (ABOS + baseline) |
| `evaluation/compare.py` | Statistical comparison of results |
| `scripts/run_agent_debug.py` | Debug runner (supports both systems) |
