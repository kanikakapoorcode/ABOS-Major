"""
ABOS LangGraph Graph Definition

Wires together all nodes into a stateful multi-agent workflow graph.

Graph flow:
  START
    → language                  (detect input language; translate to English if needed)
    → memory_retrieval          (fetch similar past feedback)
    → planner                   (LLM: decompose goal into steps)
    → compliance_plan           (compliance gate: review full plan before execution)
        → [approved]  → scheduler
        → [blocked]   → END     (plan halted, compliance_blocked status set)
    → scheduler                 (assign agents to steps via performance scores)
    → executor                  (run current step via department agent)
        → [success]  → compliance_output   (review step output for violations)
                          → should_continue?
                              → executor (next step) if more steps remain
                              → summarizer if all steps done
        → [failure]  → recovery
                          → executor (retry/reroute)
                          → next step or summarizer (if skip/abort)
    → summarizer                (LLM: generate run summary; translate back to user's language)
    → END
"""

import logging
from typing import Any, Dict, Literal

from langgraph.graph import StateGraph, START, END

from backend.agents.state import ABOSState
from backend.agents.language.language import language_node
from backend.agents.planner.planner import planner_node
from backend.agents.scheduler.scheduler import scheduler_node
from backend.agents.memory.memory import memory_retrieval_node
from backend.agents.recovery.recovery import recovery_node
from backend.agents.executor import executor_node, summarizer_node
from backend.agents.compliance.compliance import (
    compliance_plan_node,
    compliance_output_node,
)

logger = logging.getLogger(__name__)


# ── Conditional edge functions ────────────────────────────────────────────────

def route_after_planner(
    state: ABOSState,
) -> Literal["compliance_plan", END]:
    """
    If the planner failed (empty plan), go straight to END.
    Otherwise pass to the compliance plan gate.
    """
    if not state.get("workflow_plan"):
        return END
    return "compliance_plan"


def route_after_compliance_plan(
    state: ABOSState,
) -> Literal["scheduler", END]:
    """
    If the compliance plan node blocked the plan (cleared workflow_plan),
    go straight to END. Otherwise proceed to the scheduler.
    """
    if not state.get("workflow_plan"):
        return END
    return "scheduler"


def route_after_compliance_output(
    state: ABOSState,
) -> Literal["executor", "summarizer"]:
    """
    After the output compliance check:
    - If more steps remain → executor
    - If all steps done → summarizer
    The compliance_output_node may have flagged a step as compliance_failed,
    which the executor will treat as a failed step on the next iteration.
    """
    plan = state.get("workflow_plan") or []
    step_idx = state.get("current_step_index", 0)

    if step_idx >= len(plan):
        return "summarizer"
    return "executor"


def route_after_executor(
    state: ABOSState,
) -> Literal["compliance_output", "summarizer", "recovery"]:
    """
    After the executor runs a step, decide what to do next.
    - completed → compliance_output (review the output before proceeding)
    - failed / retrying → recovery
    - out of bounds → summarizer
    """
    plan = state.get("workflow_plan") or []
    # current_step_index was incremented by executor on success,
    # so check the step at index - 1 for the result.
    step_idx = state.get("current_step_index", 0)
    completed_idx = step_idx - 1

    # All steps processed
    if completed_idx >= len(plan):
        return "summarizer"

    if completed_idx >= 0:
        just_completed = plan[completed_idx]
        status = just_completed.get("status", "pending")
        if status == "completed":
            return "compliance_output"
        if status in ("failed", "retrying", "compliance_failed"):
            return "recovery"

    # If step_idx itself is still in-bounds with a failure
    if step_idx < len(plan):
        current = plan[step_idx]
        status = current.get("status", "pending")
        if status in ("failed", "retrying"):
            return "recovery"

    if step_idx >= len(plan):
        return "summarizer"

    return "compliance_output"


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


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Build and compile the ABOS LangGraph workflow graph.
    Returns a compiled graph ready for .ainvoke() calls.
    """
    graph = StateGraph(ABOSState)

    # Register nodes
    graph.add_node("language", language_node)
    graph.add_node("memory_retrieval", memory_retrieval_node)
    graph.add_node("planner", planner_node)
    graph.add_node("compliance_plan", compliance_plan_node)
    graph.add_node("scheduler", scheduler_node)
    graph.add_node("executor", executor_node)
    graph.add_node("compliance_output", compliance_output_node)
    graph.add_node("recovery", recovery_node)
    graph.add_node("summarizer", summarizer_node)

    # Entry point — language detection first
    graph.add_edge(START, "language")
    graph.add_edge("language", "memory_retrieval")
    graph.add_edge("memory_retrieval", "planner")

    # After planner: go to compliance gate or END if planner failed
    graph.add_conditional_edges(
        "planner",
        route_after_planner,
        {"compliance_plan": "compliance_plan", END: END},
    )

    # After compliance plan: proceed to scheduler or halt at END
    graph.add_conditional_edges(
        "compliance_plan",
        route_after_compliance_plan,
        {"scheduler": "scheduler", END: END},
    )

    # Scheduler always leads to executor
    graph.add_edge("scheduler", "executor")

    # After executor: review output, recover, or summarize
    graph.add_conditional_edges(
        "executor",
        route_after_executor,
        {
            "compliance_output": "compliance_output",
            "recovery": "recovery",
            "summarizer": "summarizer",
        },
    )

    # After output compliance check: next step or summarize
    graph.add_conditional_edges(
        "compliance_output",
        route_after_compliance_output,
        {
            "executor": "executor",
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
