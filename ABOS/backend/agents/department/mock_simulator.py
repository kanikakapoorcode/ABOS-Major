"""
MockSimulator — Controlled Variance Tool Execution Simulator

PURPOSE (read before changing anything):
  The research evaluation compares ABOS (adaptive scheduler) against a static
  baseline. If tools always succeed with fixed latency, both systems produce
  identical results and the comparison is meaningless.

  This simulator injects realistic variance so the scheduler has real signal
  to differentiate on across trials:
    - Failure rates  → exercises recovery module + degrades success_rate
    - Latency variance → exercises latency-based routing signal
    - Low-confidence outputs → exercises confidence-weighted routing

  Parameters come directly from SOURCE_OF_TRUTH.md §5.
  Do NOT change values without updating SOURCE_OF_TRUTH.md first.

USAGE:
  from backend.agents.department.mock_simulator import get_simulator, ToolExecutionError

  # In a tool function:
  async def my_tool(input: str) -> dict:
      sim = get_simulator()
      return await sim.run("my_tool", input, _build_output(input))

  The simulator raises ToolExecutionError on simulated failure.
  The error message always contains "tool_error" so classifier.py
  routes it as FailureType.TOOL_ERROR.
"""

import asyncio
import random
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ── Failure / latency spec per tool (SOURCE_OF_TRUTH §5) ─────────────────────

@dataclass(frozen=True)
class ToolProfile:
    failure_rate: float       # probability of raising ToolExecutionError
    latency_mean_ms: float    # normal distribution mean
    latency_std_ms: float     # normal distribution std
    low_conf_rate: float      # probability of tagging output as confidence=low


TOOL_PROFILES: Dict[str, ToolProfile] = {
    # ── Sales ──────────────────────────────────────────────────────────────
    "search_leads":     ToolProfile(0.15, 800,  150, 0.10),
    "draft_outreach":   ToolProfile(0.10, 1200, 200, 0.15),
    "update_crm":       ToolProfile(0.20, 500,  100, 0.05),
    "analyze_pipeline": ToolProfile(0.25, 1500, 300, 0.20),
    "qualify_deal":     ToolProfile(0.12, 900,  180, 0.15),
    # ── Support ────────────────────────────────────────────────────────────
    "triage_ticket":    ToolProfile(0.10, 600,  120, 0.10),
    "draft_response":   ToolProfile(0.12, 1400, 250, 0.20),
    "escalate":         ToolProfile(0.08, 400,   80, 0.05),
    "analyze_sentiment":ToolProfile(0.18, 1000, 200, 0.25),
    "get_csat_summary": ToolProfile(0.22, 1200, 250, 0.15),
    # ── Research ───────────────────────────────────────────────────────────
    "query_data":           ToolProfile(0.20, 1800, 400, 0.15),
    "analyze_trends":       ToolProfile(0.18, 2200, 500, 0.20),
    "generate_report":      ToolProfile(0.15, 2000, 400, 0.25),
    "compare_segments":     ToolProfile(0.22, 2500, 500, 0.20),
    "detect_churn_signals": ToolProfile(0.25, 2800, 600, 0.30),
}

# Fallback for any tool not in the table above
_DEFAULT_PROFILE = ToolProfile(0.10, 1000, 200, 0.10)


# ── Exception ─────────────────────────────────────────────────────────────────

class ToolExecutionError(Exception):
    """
    Raised by the simulator on a simulated tool failure.

    The message always contains "tool_error" so that
    classifier.classify_failure() routes this as FailureType.TOOL_ERROR.
    """
    def __init__(self, tool_name: str, reason: str = "simulated failure"):
        self.tool_name = tool_name
        super().__init__(f"tool_error: {tool_name} failed — {reason}")


# ── Simulator ─────────────────────────────────────────────────────────────────

class MockSimulator:
    """
    Seeded stochastic simulator for tool execution.

    seed=None  → random seed each time (use for evaluation trials)
    seed=int   → deterministic (use for unit tests and debugging)

    Thread/async safety: each instance has its own Random instance.
    Do NOT share one simulator across concurrent coroutines.
    """

    def __init__(self, seed: Optional[int] = None):
        self._seed = seed if seed is not None else random.randint(0, 99_999)
        self._rng = random.Random(self._seed)
        logger.debug(f"[MockSimulator] initialised with seed={self._seed}")

    @property
    def seed(self) -> int:
        return self._seed

    def _profile(self, tool_name: str) -> ToolProfile:
        return TOOL_PROFILES.get(tool_name, _DEFAULT_PROFILE)

    def _sample_latency(self, profile: ToolProfile) -> float:
        """Sample latency from N(mean, std), clamped to [50, mean*3]."""
        raw = self._rng.gauss(profile.latency_mean_ms, profile.latency_std_ms)
        return max(50.0, min(raw, profile.latency_mean_ms * 3))

    def _should_fail(self, profile: ToolProfile) -> bool:
        return self._rng.random() < profile.failure_rate

    def _confidence(self, profile: ToolProfile) -> str:
        if self._rng.random() < profile.low_conf_rate:
            return "low"
        # Medium confidence at half the remaining probability
        if self._rng.random() < 0.25:
            return "medium"
        return "high"

    async def run(
        self,
        tool_name: str,
        result_payload: Any,
    ) -> Dict[str, Any]:
        """
        Simulate one tool execution.

        Parameters
        ----------
        tool_name      : name of the tool (must match TOOL_PROFILES key)
        result_payload : the actual result string/dict to return on success

        Returns
        -------
        dict with keys: result, confidence, simulated_latency_ms, tool_name, success

        Raises
        ------
        ToolExecutionError on simulated failure (after sleeping the sampled latency)
        """
        profile = self._profile(tool_name)
        latency = self._sample_latency(profile)

        # Simulate real wall-clock latency so base.py's time.monotonic() captures it
        await asyncio.sleep(latency / 1000.0)

        if self._should_fail(profile):
            logger.debug(
                f"[MockSimulator] {tool_name} FAILED "
                f"(latency={latency:.0f}ms, seed={self._seed})"
            )
            raise ToolExecutionError(tool_name)

        confidence = self._confidence(profile)
        logger.debug(
            f"[MockSimulator] {tool_name} OK "
            f"(latency={latency:.0f}ms, confidence={confidence}, seed={self._seed})"
        )

        return {
            "result": result_payload,
            "confidence": confidence,
            "simulated_latency_ms": round(latency, 2),
            "tool_name": tool_name,
            "success": True,
        }


# ── Module-level instance ─────────────────────────────────────────────────────
# Used by all tool functions at runtime.
# Replaced with a seeded instance during evaluation trials via set_simulator().

_simulator: MockSimulator = MockSimulator(seed=None)


def get_simulator() -> MockSimulator:
    """Return the current module-level simulator instance."""
    return _simulator


def set_simulator(sim: MockSimulator) -> None:
    """
    Replace the module-level simulator.
    Call this from the evaluation runner before each trial to inject a
    known seed, ensuring reproducibility when needed.

    Example:
        from backend.agents.department.mock_simulator import set_simulator, MockSimulator
        set_simulator(MockSimulator(seed=trial_seed))
    """
    global _simulator
    _simulator = sim
    logger.info(f"[MockSimulator] replaced with seed={sim.seed}")
