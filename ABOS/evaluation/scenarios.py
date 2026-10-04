"""
Evaluation scenarios — single source of truth for all 9 test cases.

Mirrors SOURCE_OF_TRUTH.md Section 6 and scripts/run_agent_debug.py SCENARIOS.
Both files must stay in sync. If you change a scenario here, update both.
"""

from typing import Dict, Any, List

SCENARIOS: Dict[str, Dict[str, Any]] = {
    "S1": {
        "title": "Q4 Cold Lead Outreach",
        "description": (
            "Identify enterprise leads with no activity in 90 days, "
            "draft personalized outreach messages for the top 10, "
            "and update the CRM with sent status."
        ),
        "priority": "high",
        "target_departments": ["sales"],
        "department": "sales",
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
        "department": "sales",
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
        "department": "sales",
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
        "department": "support",
    },
    "P2": {
        "title": "CSAT Improvement Plan",
        "description": (
            "Analyze last month low-rated support tickets, "
            "identify the top recurring complaint themes, "
            "and draft a concrete improvement recommendation plan."
        ),
        "priority": "medium",
        "target_departments": ["support"],
        "department": "support",
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
        "department": "support",
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
        "department": "research",
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
        "department": "research",
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
        "department": "research",
    },
}

SCENARIO_IDS: List[str] = list(SCENARIOS.keys())
DEPARTMENTS: List[str] = ["sales", "support", "research"]
