"""
Scheduler scoring formula — Research Contribution #2

Computes a composite routing score for each agent based on:
  - success_rate  : rolling window fraction of successful executions
  - latency_score : normalized inverse latency (lower latency = higher score)
  - confidence    : persisted composite score updated by feedback

This is a lightweight, interpretable, non-RL approach — explicitly positioned
as a practical alternative to MetaAgent-X's end-to-end RL scheduler.

Weights are configurable via environment variables / config.
"""

import math
from dataclasses import dataclass
from typing import Optional


# ── Scoring weights ───────────────────────────────────────────────────────────
# Adjust these to tune scheduler behaviour.
# They must sum to 1.0.
WEIGHT_SUCCESS_RATE: float = 0.50
WEIGHT_LATENCY: float = 0.20
WEIGHT_CONFIDENCE: float = 0.30

# Latency normalization reference point (ms).
# A step with this latency gets a latency score of ~0.5.
LATENCY_REFERENCE_MS: float = 3000.0


@dataclass
class AgentScoreInput:
    """All data needed to score a single agent for a single step."""
    agent_name: str
    department: str
    success_rate: float          # 0.0 – 1.0
    avg_latency_ms: float        # milliseconds (0 means no data yet)
    confidence_score: float      # 0.0 – 1.0
    total_executions: int


@dataclass
class AgentScoreResult:
    agent_name: str
    department: str
    composite_score: float
    success_rate: float
    latency_score: float
    confidence_score: float


def latency_score(avg_latency_ms: float, total_executions: int = 1) -> float:
    """
    Map average latency to a 0–1 score where lower latency = higher score.
    Uses a sigmoid-like inverse: score = 1 / (1 + latency / reference)

    If total_executions == 0 (cold start) or avg_latency_ms <= 0 (missing/invalid data),
    returns 0.5 (neutral fallback). Never treats missing data as perfect latency (1.0).

    Examples:
      0 ms or cold-start → 0.5  (neutral prior / missing data)
      3000 ms           → 0.5  (reference point)
      9000 ms           → 0.25
    """
    if total_executions <= 0 or avg_latency_ms <= 0:
        return 0.5  # neutral fallback for unexecuted or missing latency
    return 1.0 / (1.0 + avg_latency_ms / LATENCY_REFERENCE_MS)


def cold_start_score(agent_name: str = "unknown", department: str = "unknown") -> AgentScoreResult:
    """
    Cold-start prior for an agent with no execution history.
    Returns neutral priors (composite_score = 0.41) representing 'no evidence yet'.
    0.50 * 0.5 (success_rate) + 0.20 * 0.5 (latency_score) + 0.30 * 0.2 (confidence) = 0.41
    """
    return AgentScoreResult(
        agent_name=agent_name,
        department=department,
        composite_score=0.41,
        success_rate=0.5,
        latency_score=0.5,
        confidence_score=0.2,
    )


def compute_score(agent: AgentScoreInput) -> AgentScoreResult:
    """
    Compute composite routing score for one agent.

    score = w_s * success_rate
          + w_l * latency_score(avg_latency_ms)
          + w_c * confidence_score
    """
    if agent.total_executions == 0:
        return cold_start_score(agent_name=agent.agent_name, department=agent.department)

    ls = latency_score(agent.avg_latency_ms, total_executions=agent.total_executions)

    composite = (
        WEIGHT_SUCCESS_RATE * agent.success_rate
        + WEIGHT_LATENCY * ls
        + WEIGHT_CONFIDENCE * agent.confidence_score
    )
    # Clamp to [0, 1]
    composite = max(0.0, min(1.0, composite))

    return AgentScoreResult(
        agent_name=agent.agent_name,
        department=agent.department,
        composite_score=round(composite, 4),
        success_rate=agent.success_rate,
        latency_score=round(ls, 4),
        confidence_score=agent.confidence_score,
    )


def select_best_agent(candidates: list[AgentScoreInput]) -> Optional[AgentScoreResult]:
    """
    Given a list of candidate agents for a department, return the one with
    the highest composite score.
    Returns None if the list is empty.

    Cold-Start Tie-Breaking Policy:
    When candidate scores are tied (e.g. all unexecuted at cold-start prior 0.41),
    max() deterministically selects the first candidate in the list (configured primary agent).
    """
    if not candidates:
        return None
    scored = [compute_score(a) for a in candidates]
    return max(scored, key=lambda r: r.composite_score)


def update_confidence_score(
    current_confidence: float,
    execution_succeeded: bool,
    feedback_correct: Optional[bool],
    alpha: float = 0.1,
) -> float:
    """
    Exponential moving average update for confidence score.

    Positive signal: execution succeeded AND (no feedback OR feedback correct)
    Negative signal: execution failed OR feedback marked incorrect

    alpha: learning rate (0.1 = slow adaptation, 0.3 = fast)
    """
    if execution_succeeded and feedback_correct is not False:
        signal = 1.0
    elif not execution_succeeded or feedback_correct is False:
        signal = 0.0
    else:
        signal = 0.5  # partial / uncertain

    new_confidence = (1 - alpha) * current_confidence + alpha * signal
    return round(max(0.0, min(1.0, new_confidence)), 4)
