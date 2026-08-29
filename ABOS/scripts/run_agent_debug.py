"""
ABOS Agent Debug Runner
=======================
Invokes the LangGraph graph directly — no API, no Celery, no DB writes.
Use this to verify end-to-end graph execution during development.

Usage
-----
  # Default scenario (Sales Q4 outreach)
  poetry run python scripts/run_agent_debug.py

  # Choose a scenario
  poetry run python scripts/run_agent_debug.py --scenario S2

  # Use a fixed seed (deterministic tool outcomes)
  poetry run python scripts/run_agent_debug.py --seed 42

  # Disable memory retrieval (faster, no DB needed)
  poetry run python scripts/run_agent_debug.py --no-memory

  # Show full state dump at the end
  poetry run python scripts/run_agent_debug.py --verbose

Available scenarios: S1 S2 S3 P1 P2 P3 R1 R2 R3
(See SOURCE_OF_TRUTH.md §6 for scenario definitions)
"""

import argparse
import asyncio
import json
import logging
import sys
import time
import os

# Ensure project root is on path when run directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("debug_runner")

# ── Scenario definitions (mirrors SOURCE_OF_TRUTH §6) ────────────────────────

SCENARIOS = {
    "S1": {
        "title": "Q4 Cold Lead Outreach",
        "description": (
            "Identify enterprise leads with no activity in 90 days, "
            "draft personalized outreach messages for the top 10, "
            "and update the CRM with sent status."
        ),
        "priority": "high",
        "target_departments": ["sales"],
    },
    "S2": {
        "title": "Pipeline Health Review",
        "description": (
            "Analyze the current sales pipeline for at-risk deals, "
            "qualify the top 5 highest-value opportunities using BANT criteria, "
            "and generate a priority action list for the sales team."
        ),
        "priority": "high",
        "target_departments": ["sales"],
    },
    "S3": {
        "title": "Win/Loss Analysis",
        "description": (
            "Compare closed-won versus closed-lost deals in the last quarter, "
            "identify the top 3 loss reasons, "
            "and recommend strategy adjustments for the next quarter."
        ),
        "priority": "medium",
        "target_departments": ["sales", "research"],
    },
    "P1": {
        "title": "Ticket Backlog Triage",
        "description": (
            "Triage the open ticket backlog by priority and type, "
            "draft responses for the top 10 high-priority tickets, "
            "and flag any tickets requiring escalation."
        ),
        "priority": "high",
        "target_departments": ["support"],
    },
    "P2": {
        "title": "CSAT Improvement Plan",
        "description": (
            "Analyze last month's low-rated support tickets, "
            "identify the top recurring complaint themes, "
            "and draft a concrete improvement recommendation plan."
        ),
        "priority": "medium",
        "target_departments": ["support"],
    },
    "P3": {
        "title": "Escalation Review",
        "description": (
            "Review all escalated tickets from the last 2 weeks, "
            "classify each by root cause, "
            "and draft resolution summaries for the management report."
        ),
        "priority": "medium",
        "target_departments": ["support"],
    },
    "R1": {
        "title": "Monthly KPI Report",
        "description": (
            "Query all key business metrics for the last 30 days, "
            "identify significant trends, "
            "and generate an executive summary report."
        ),
        "priority": "medium",
        "target_departments": ["research"],
    },
    "R2": {
        "title": "Churn Risk Analysis",
        "description": (
            "Detect customers showing churn signals in the last 30 days, "
            "compare their behaviour against the retained segment, "
            "and output a risk-scored list of at-risk accounts."
        ),
        "priority": "high",
        "target_departments": ["research"],
    },
    "R3": {
        "title": "Segment Comparison",
        "description": (
            "Compare enterprise versus SMB customer segments "
            "on engagement and revenue metrics, "
            "and identify the top 3 key differentiators."
        ),
        "priority": "medium",
        "target_departments": ["research"],
    },
}


# ── Patched memory node (skips DB when --no-memory) ──────────────────────────

async def _noop_memory_node(state):
    return {"retrieved_memory": [], "logs": ["Memory: skipped (--no-memory flag)."]}


# ── Main runner ───────────────────────────────────────────────────────────────

async def run(scenario_id: str, seed: int | None, no_memory: bool, verbose: bool):
    scenario = SCENARIOS[scenario_id]

    # Inject simulator seed before importing graph
    from backend.agents.department.mock_simulator import set_simulator, MockSimulator
    effective_seed = seed if seed is not None else None
    sim = MockSimulator(seed=effective_seed)
    set_simulator(sim)
    logger.info(f"MockSimulator seed: {sim.seed}")

    # Build graph — patch memory node if --no-memory
    if no_memory:
        import backend.agents.memory.memory as mem_module
        mem_module.memory_retrieval_node = _noop_memory_node

    from backend.agents.graph import build_graph
    graph = build_graph()

    initial_state = {
        "goal_id": f"debug-{scenario_id}",
        "workflow_id": f"debug-wf-{scenario_id}",
        "user_id": "debug-user",
        "goal_title": scenario["title"],
        "goal_description": scenario["description"],
        "goal_priority": scenario["priority"],
        "goal_context": {"debug": True, "seed": sim.seed},
        "target_departments": scenario.get("target_departments"),
        "workflow_plan": None,
        "current_step_index": 0,
        "completed_steps": [],
        "failed_steps": [],
        "retrieved_memory": [],
        "recovery_attempts": 0,
        "max_recovery_attempts": 3,
        "final_status": None,
        "summary": None,
        "error": None,
        "logs": [],
    }

    print("\n" + "═" * 60)
    print(f"  ABOS DEBUG RUNNER")
    print(f"  Scenario : {scenario_id} — {scenario['title']}")
    print(f"  Seed     : {sim.seed}")
    print(f"  Memory   : {'disabled' if no_memory else 'enabled'}")
    print("═" * 60 + "\n")

    start = time.monotonic()

    try:
        result = await graph.ainvoke(initial_state)
    except Exception as e:
        logger.error(f"Graph raised exception: {e}", exc_info=True)
        print(f"\n❌ Graph failed with exception: {e}")
        return

    elapsed = time.monotonic() - start

    # ── Summary ───────────────────────────────────────────────────────────────
    plan = result.get("workflow_plan") or []
    completed = result.get("completed_steps") or []
    failed = result.get("failed_steps") or []

    print("─" * 60)
    print(f"  Status   : {result.get('final_status', 'unknown').upper()}")
    print(f"  Steps    : {len(completed)}/{len(plan)} completed, {len(failed)} failed")
    print(f"  Elapsed  : {elapsed:.2f}s")
    print("─" * 60)

    if result.get("summary"):
        print(f"\nSummary:\n  {result['summary']}\n")

    # ── Step table ────────────────────────────────────────────────────────────
    print("Steps:")
    for step in plan:
        icon = {"completed": "✅", "failed": "❌", "skipped": "⏭"}.get(
            step.get("status", ""), "⏳"
        )
        latency = f"{step.get('latency_ms', 0):.0f}ms" if step.get("latency_ms") else "—"
        score = f"{step.get('scheduler_score', 0):.3f}" if step.get("scheduler_score") else "—"
        print(
            f"  {icon} [{step['assigned_department']:<8}] "
            f"{step['title'][:40]:<40} "
            f"lat={latency:<8} score={score}"
        )
        if step.get("error_message"):
            print(f"       ↳ error: {step['error_message']}")

    # ── Logs ──────────────────────────────────────────────────────────────────
    logs = result.get("logs") or []
    if logs:
        print(f"\nLogs ({len(logs)} entries):")
        for log in logs:
            print(f"  · {log}")

    # ── Full state dump (--verbose) ───────────────────────────────────────────
    if verbose:
        print("\nFull state dump:")
        # Remove large output fields for readability
        dump = {
            k: v for k, v in result.items()
            if k not in ("workflow_plan",)
        }
        print(json.dumps(dump, indent=2, default=str))

    print("\n" + "═" * 60 + "\n")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ABOS agent debug runner")
    parser.add_argument(
        "--scenario",
        default="S1",
        choices=list(SCENARIOS.keys()),
        help="Scenario ID to run (default: S1)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Fixed random seed for MockSimulator (default: random)",
    )
    parser.add_argument(
        "--no-memory",
        action="store_true",
        help="Skip memory retrieval (no DB connection needed)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print full state dump at end",
    )
    args = parser.parse_args()

    asyncio.run(
        run(
            scenario_id=args.scenario,
            seed=args.seed,
            no_memory=args.no_memory,
            verbose=args.verbose,
        )
    )


if __name__ == "__main__":
    main()
