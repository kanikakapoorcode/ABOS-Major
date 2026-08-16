"""
ABOS LangGraph shared state definition.

ABOSState is the single typed dict that flows through every node in the graph.
LangGraph passes it between nodes; each node reads what it needs and writes its outputs back.
"""

from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict
import operator


class WorkflowStepState(TypedDict):
    """Represents one step in the generated workflow plan."""
    step_index: int
    title: str
    description: str
    assigned_department: str        # "sales" | "support" | "research"
    assigned_agent: str             # specific agent identifier
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]]
    status: str                     # pending | running | completed | failed | retrying
    retry_count: int
    latency_ms: Optional[float]
    scheduler_score: Optional[float]
    error_message: Optional[str]


class ABOSState(TypedDict):
    """
    Global state object passed through the LangGraph workflow graph.

    Fields are annotated with operators where LangGraph needs to merge
    parallel node outputs (e.g. messages use operator.add to append).
    """

    # ── Input ──────────────────────────────────────────────────────────────
    goal_id: str
    workflow_id: str
    user_id: str
    goal_title: str
    goal_description: str
    goal_priority: str
    goal_context: Optional[Dict[str, Any]]
    target_departments: Optional[List[str]]

    # ── Planning ───────────────────────────────────────────────────────────
    workflow_plan: Optional[List[WorkflowStepState]]   # output of the planner node
    current_step_index: int

    # ── Execution ──────────────────────────────────────────────────────────
    # Using Annotated + operator.add so parallel step outputs are merged
    completed_steps: Annotated[List[WorkflowStepState], operator.add]
    failed_steps: Annotated[List[WorkflowStepState], operator.add]

    # ── Memory / context ───────────────────────────────────────────────────
    retrieved_memory: Optional[List[Dict[str, Any]]]  # similar past feedback from pgvector

    # ── Recovery ───────────────────────────────────────────────────────────
    recovery_attempts: int
    max_recovery_attempts: int

    # ── Final output ───────────────────────────────────────────────────────
    final_status: Optional[str]     # completed | failed | partially_completed
    summary: Optional[str]          # LLM-generated summary of the run
    error: Optional[str]

    # ── Diagnostic / tracing ───────────────────────────────────────────────
    logs: Annotated[List[str], operator.add]
