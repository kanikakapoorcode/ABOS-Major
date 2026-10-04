"""
Failure Classifier

Adopted from Self-Healing Agentic Orchestrators (2026) — cited, not claimed as novel.

Classifies execution failures into recoverable types to guide the recovery strategy.
"""

from enum import Enum


class FailureType(str, Enum):
    TIMEOUT = "timeout"
    LLM_ERROR = "llm_error"          # transient LLM API error
    TOOL_ERROR = "tool_error"        # tool call raised an exception
    INVALID_OUTPUT = "invalid_output" # LLM output failed validation
    REROUTE = "reroute"              # agent consistently failing — try different agent
    UNRECOVERABLE = "unrecoverable"  # max retries exceeded or unknown error


class RecoveryAction(str, Enum):
    RETRY = "retry"                  # retry same agent, same step
    RETRY_WITH_TIMEOUT = "retry_with_timeout"
    REROUTE = "reroute"              # try a different agent for this department
    SKIP = "skip"                    # mark step failed, move to next
    ABORT = "abort"                  # abort the entire workflow


def classify_failure(error_message: str, retry_count: int, max_retries: int) -> FailureType:
    """
    Classify a failure based on the error message and retry history.

    This is a rule-based classifier — appropriate for the project scope.
    Could be replaced with an LLM classifier for more nuance.
    """
    if retry_count >= max_retries:
        return FailureType.UNRECOVERABLE

    err = error_message.lower()

    if any(kw in err for kw in ["timeout", "timed out", "deadline"]):
        return FailureType.TIMEOUT
    if any(kw in err for kw in ["rate limit", "quota", "429", "503", "overloaded"]):
        return FailureType.LLM_ERROR
    if any(kw in err for kw in ["tool", "function call", "tool_error"]):
        return FailureType.TOOL_ERROR
    if any(kw in err for kw in ["invalid", "json", "parse", "validation"]):
        return FailureType.INVALID_OUTPUT
    if retry_count >= 2:
        return FailureType.REROUTE

    return FailureType.LLM_ERROR  # default: treat as transient


def decide_recovery_action(
    failure_type: FailureType,
    retry_count: int,
    max_retries: int,
    has_alternative_agent: bool = False,
) -> RecoveryAction:
    """
    Given a failure type, decide what recovery action to take.
    Maps to the bounded recovery budget approach from Self-Healing Orchestrators (2026).
    """
    if failure_type == FailureType.UNRECOVERABLE:
        return RecoveryAction.SKIP

    if failure_type == FailureType.TIMEOUT:
        return RecoveryAction.RETRY_WITH_TIMEOUT

    if failure_type == FailureType.REROUTE:
        if has_alternative_agent:
            return RecoveryAction.REROUTE
        return RecoveryAction.SKIP

    if failure_type in (FailureType.LLM_ERROR, FailureType.TOOL_ERROR, FailureType.INVALID_OUTPUT):
        if retry_count < max_retries:
            return RecoveryAction.RETRY
        return RecoveryAction.SKIP

    return RecoveryAction.SKIP
