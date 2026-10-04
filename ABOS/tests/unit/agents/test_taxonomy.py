"""
Unit tests for Canonical Task Taxonomy.
"""

from backend.agents.tasks.taxonomy import (
    validate_task_type,
    CANONICAL_TASK_TYPES,
    MIN_TASK_EVIDENCE,
    MIN_AGGREGATE_EVIDENCE,
)


def test_taxonomy_constants():
    assert len(CANONICAL_TASK_TYPES["sales"]) == 5
    assert len(CANONICAL_TASK_TYPES["support"]) == 5
    assert len(CANONICAL_TASK_TYPES["research"]) == 5
    assert MIN_TASK_EVIDENCE == 3
    assert MIN_AGGREGATE_EVIDENCE == 1


def test_validate_task_type_exact_matches():
    assert validate_task_type("sales", "lead_search") == "lead_search"
    assert validate_task_type("support", "ticket_triage") == "ticket_triage"
    assert validate_task_type("research", "churn_detection") == "churn_detection"


def test_validate_task_type_case_and_whitespace():
    assert validate_task_type("sales", "  CRM_UPDATE  ") == "crm_update"
    assert validate_task_type("SUPPORT", "csat_analysis") == "csat_analysis"


def test_validate_task_type_invalid_and_cross_department():
    # Invalid task type
    assert validate_task_type("sales", "random_unregistered_task") is None
    # Valid task type for wrong department must return None
    assert validate_task_type("sales", "ticket_triage") is None
    assert validate_task_type("support", "lead_search") is None
    # None or non-string
    assert validate_task_type("sales", None) is None
    assert validate_task_type("sales", "") is None
