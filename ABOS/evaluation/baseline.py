"""
ABOS Baseline System
====================
Static-workflow baseline for evaluation comparison.

Implements the spec in docs/BASELINE_SPEC.md exactly.

The only differences from ABOS:
  1. Fixed routing policy (no scheduler scoring)
  2. Memory retrieval disabled (no pgvector lookup)
  3. Agent profiles NOT updated after execution

Everything else — planner, agents, tools, MockSimulator, recovery module —
is identical to ABOS. Same seed is used for paired trials.

Do NOT modify this file to produce a particular result.
Changes must be documented in BASELINE_SPEC.md first.
"""

import logging
from typing import Any, Dict, List, Literal

from langgraph.graph import StateGraph, START, END

from backend.agents.state import ABOSState

logger = logging.getLogger(__name__)

# ── Fixed routing table (BASELINE_SPEC §2) ────────────────────────────────────

BASELINE_ROUTING: Dict[str, str] = {
    "sales":    "sales_outreach_fast",
    "support":  "support_tier1_fast",
    "research": "research_kpi_quick",
}


# ── Noop memory node (BASELINE_SPEC §3.1) ────────────────────────────────────

async def noop_memory_node(state: ABOSState) -> Dict[str, Any]:
    """
    Memory retrieval disabled in baseline.
    Returns empty retrieved_memory so the planner gets no past feedback context.
    """
    return {
        "retrieved_memory": [],
        "logs": ["Baseline: memory retrieval disabled."],
    }


# ── Baseline scheduler node (BASELINE_SPEC §6) ───────────────────────────────

async def baseline_scheduler_node(state: ABOSState) -> Dict[str, Any]:
    """
    Fixed routing: assigns the single registered agent for each step's
    department. No scoring. No profile lookup. No DB access.
    scheduler_score is explicitly set to None on all steps.
    """
    plan = state.get("workflow_plan") or []
    if not plan:
        return {"logs": ["Baseline scheduler: no steps to route."]}

    scheduled = []
    for step in plan:
        updated = dict(step)
        dept = step.get("assigned_department", "research")
        updated["assigned_agent"] = BASELINE_ROUTING.get(dept, f"{dept}_agent")
        updated["scheduler_score"] = None   # None marks this as a baseline run
        scheduled.append(updated)

    logger.info(
        f"[BaselineScheduler] Fixed routing for {len(scheduled)} steps "
        f"(goal_id={state['goal_id']})"
    )

    return {
        "workflow_plan": scheduled,
        "logs": [f"Baseline scheduler: fixed routing for {len(scheduled)} steps."],
    }


# ── Baseline graph builder ────────────────────────────────────────────────────

def build_baseline_graph() -> StateGraph:
    """
    Build the baseline LangGraph graph.

    Identical to ABOS graph (`backend/agents/graph.py`) except:
      - memory_retrieval  → noop_memory_node
      - scheduler         → baseline_scheduler_node

    All other nodes and routing functions (language, compliance_plan,
    compliance_output, executor, recovery, summarizer) are imported directly
    from the ABOS implementation so the routing policy is the sole difference.
    """
    from backend.agents.language.language import language_node
    from backend.agents.planner.planner import planner_node
    from backend.agents.compliance.compliance import (
        compliance_plan_node,
        compliance_output_node,
    )
    from backend.agents.recovery.recovery import recovery_node
    from backend.agents.executor import executor_node, summarizer_node
    from backend.agents.graph import (
        route_after_planner,
        route_after_compliance_plan,
        route_after_executor,
        route_after_compliance_output,
        route_after_recovery,
    )

    graph = StateGraph(ABOSState)

    # Nodes
    graph.add_node("language",             language_node)            # identical
    graph.add_node("memory_retrieval",     noop_memory_node)         # disabled
    graph.add_node("planner",              planner_node)             # identical
    graph.add_node("compliance_plan",      compliance_plan_node)     # identical
    graph.add_node("baseline_scheduler",   baseline_scheduler_node)  # fixed routing
    graph.add_node("executor",             executor_node)            # identical
    graph.add_node("compliance_output",    compliance_output_node)   # identical
    graph.add_node("recovery",             recovery_node)            # identical
    graph.add_node("summarizer",           summarizer_node)          # identical

    # Edges — exact mirror of backend/agents/graph.py
    graph.add_edge(START, "language")
    graph.add_edge("language", "memory_retrieval")
    graph.add_edge("memory_retrieval", "planner")

    graph.add_conditional_edges(
        "planner",
        route_after_planner,
        {"compliance_plan": "compliance_plan", END: END},
    )

    graph.add_conditional_edges(
        "compliance_plan",
        route_after_compliance_plan,
        {"scheduler": "baseline_scheduler", END: END},
    )

    graph.add_edge("baseline_scheduler", "executor")

    graph.add_conditional_edges(
        "executor",
        route_after_executor,
        {
            "compliance_output": "compliance_output",
            "recovery": "recovery",
            "summarizer": "summarizer",
        },
    )

    graph.add_conditional_edges(
        "compliance_output",
        route_after_compliance_output,
        {
            "executor": "executor",
            "summarizer": "summarizer",
        },
    )

    graph.add_conditional_edges(
        "recovery",
        route_after_recovery,
        {"executor": "executor", "summarizer": "summarizer"},
    )

    graph.add_edge("summarizer", END)

    return graph.compile()


# ── Convenience runner ────────────────────────────────────────────────────────

async def run_baseline(
    scenario: Dict[str, Any],
    seed: int,
    scenario_id: str = "unknown",
) -> Dict[str, Any]:
    """
    Run one baseline trial for a given scenario and seed.

    Parameters
    ----------
    scenario    : dict with keys title, description, priority, target_departments
    seed        : MockSimulator seed (must match paired ABOS trial seed)
    scenario_id : label for logging

    Returns
    -------
    The final ABOSState dict after graph execution.
    """
    import uuid
    from backend.agents.department.mock_simulator import set_simulator, MockSimulator

    # Inject seed — must be called before graph runs any tools
    set_simulator(MockSimulator(seed=seed))

    graph = build_baseline_graph()

    initial_state: ABOSState = {
        "goal_id":              f"baseline-{scenario_id}-{seed}",
        "workflow_id":          f"baseline-wf-{scenario_id}-{seed}",
        "user_id":              "eval-runner",
        "goal_title":           scenario["title"],
        "goal_description":     scenario["description"],
        "goal_priority":        scenario.get("priority", "medium"),
        "goal_context":         {"system": "baseline", "seed": seed},
        "target_departments":   scenario.get("target_departments"),
        "workflow_plan":        None,
        "current_step_index":   0,
        "completed_steps":      [],
        "failed_steps":         [],
        "retrieved_memory":     [],
        "recovery_attempts":    0,
        "max_recovery_attempts": 3,
        "final_status":         None,
        "summary":              None,
        "error":                None,
        "logs":                 [],
    }

    logger.info(f"[Baseline] Running scenario={scenario_id} seed={seed}")

    try:
        result = await graph.ainvoke(initial_state)
    except Exception as e:
        logger.error(f"[Baseline] Graph exception for {scenario_id}: {e}", exc_info=True)
        result = dict(initial_state)
        result["final_status"] = "failed"
        result["error"] = str(e)

    return result
