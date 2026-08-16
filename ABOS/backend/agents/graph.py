"""
ABOS LangGraph Graph Definition

Wires together all nodes into a stateful multi-agent workflow graph.

Graph flow:
  START
    → memory_retrieval        (fetch similar past feedback)
    → planner                 (LLM: decompose goal into steps)
    → scheduler               (assign agents to steps via performance scores)
    → executor                (run current step via department agent)
        → [success]  → should_continue?
                          → executor (next step) if more steps remain
                          → summarizer if all steps done
        → [failure]  → recovery
                          → executor (retry/reroute)
                          → next step or summarizer (if skip/abort)
    → summarizer              (LLM: generate run summary)
    → END
"""

import logging
from typing import Any, Dict, Literal

from langgraph.graph import StateGraph, START, END

from backend.agents.state import ABOSState
from backend.agents.planner.planner import planner_node
from backend.agents.scheduler.scheduler import scheduler_node
from backend.agents.memory.memory import memory_retrieval_node
from backend.agents.recovery.recovery import recovery_node
from backend.agents.executor import executor_node, summarizer_node

logger = logging.getLogger(__name__)


# ── Conditional edge functions ────────────────────────────────────────────────

def route_after_executor(
    state: ABOSState,
) -> Literal["executor", "summarizer", "recovery"]:
    """
    After the executor runs a step, decide what to do next.
    """
    plan = state.get("workflow_plan") or []
    step_idx = state.get("current_step_index", 0)

    if step_idx >= len(plan):
        # All steps processed
        return "summarizer"

    current_step = plan[step_idx]
    status = current_step.get("status", "pending")

    if status == "failed" or status == "retrying":
        return "recovery"

    # Check if there are more steps to run
    next_idx = step_idx + 1
    if next_idx >= len(plan):
        return "summarizer"

    return "executor"


def route_after_recovery(
    state: ABOSState,
) -> Literal["executor", "summarizer"]:
    """
    After recovery, either retry the step (executor) or move on (summarizer).
    """
    plan = state.get("workflow_plan") or []
    step_idx = state.get("current_step_index", 0)

    if step_idx >= len(plan):
        return "summarizer"

    current_step = plan[step_idx]
    status = current_step.get("status", "pending")

    if status == "retrying":
        return "executor"

    # Step was skipped or aborted — check if there are more steps
    if step_idx < len(plan):
        return "executor"

    return "summarizer"


def route_after_planner(
    state: ABOSState,
) -> Literal["scheduler", END]:
    """
    If the planner failed (empty plan), go straight to END.
    """
    if not state.get("workflow_plan"):
        return END
    return "scheduler"


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Build and compile the ABOS LangGraph workflow graph.
    Returns a compiled graph ready for .ainvoke() calls.
    """
    graph = StateGraph(ABOSState)

    # Register nodes
    graph.add_node("memory_retrieval", memory_retrieval_node)
    graph.add_node("planner", planner_node)
    graph.add_node("scheduler", scheduler_node)
    graph.add_node("executor", executor_node)
    graph.add_node("recovery", recovery_node)
    graph.add_node("summarizer", summarizer_node)

    # Entry point
    graph.add_edge(START, "memory_retrieval")
    graph.add_edge("memory_retrieval", "planner")

    # After planner: go to scheduler or END if planner failed
    graph.add_conditional_edges(
        "planner",
        route_after_planner,
        {"scheduler": "scheduler", END: END},
    )

    # Scheduler always leads to executor
    graph.add_edge("scheduler", "executor")

    # After executor: retry, next step, or summarize
    graph.add_conditional_edges(
        "executor",
        route_after_executor,
        {
            "executor": "executor",
            "recovery": "recovery",
            "summarizer": "summarizer",
        },
    )

    # After recovery: retry via executor or summarize
    graph.add_conditional_edges(
        "recovery",
        route_after_recovery,
        {
            "executor": "executor",
            "summarizer": "summarizer",
        },
    )

    # Summarizer always leads to END
    graph.add_edge("summarizer", END)

    return graph.compile()


# Module-level compiled graph instance
# Import this in workers/tasks.py
abos_graph = build_graph()
