"""
Canonical Task Taxonomy & Validation for ABOS.

Defines the closed-set canonical task types per department and the
evidence sufficiency threshold for task-conditioned routing.
"""

from typing import Dict, Optional, Set

# Evidence sufficiency thresholds
MIN_TASK_EVIDENCE: int = 3  # Minimum executions required to trust task-specific stats
MIN_AGGREGATE_EVIDENCE: int = 1  # Minimum executions required to trust aggregate stats

# Closed-set canonical task types per department
CANONICAL_TASK_TYPES: Dict[str, Set[str]] = {
    "sales": {
        "lead_search",
        "outreach_drafting",
        "crm_update",
        "pipeline_analysis",
        "deal_qualification",
    },
    "support": {
        "ticket_triage",
        "response_drafting",
        "ticket_escalation",
        "sentiment_analysis",
        "csat_analysis",
    },
    "research": {
        "data_query",
        "trend_analysis",
        "report_generation",
        "segment_comparison",
        "churn_detection",
    },
}


def validate_task_type(department: str, raw_task_type: Optional[str]) -> Optional[str]:
    """
    Validate and return the canonical task_type for a department.

    Strict enforcement:
    - If raw_task_type is valid for the department, returns it.
    - If raw_task_type is unknown, invalid, or missing, returns None.
    - Never guesses or fuzzes unknown strings.
    """
    if not raw_task_type or not isinstance(raw_task_type, str):
        return None

    cleaned = raw_task_type.strip().lower()
    allowed = CANONICAL_TASK_TYPES.get(department.lower(), set())

    if cleaned in allowed:
        return cleaned

    return None
