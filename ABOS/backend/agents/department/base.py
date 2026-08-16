"""
Base class for all ABOS department agents.

Each department agent:
- Has a name, department, and list of LangChain tools
- Builds a LangChain ReAct agent (LLM + tools) internally
- Exposes a single async execute() method that the graph calls

To add a new department agent, subclass BaseDepartmentAgent,
set name/department/tools, and implement _get_system_prompt().
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from langchain_core.tools import BaseTool
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from litellm import acompletion

from backend.agents.state import WorkflowStepState
from backend.core.config import settings

logger = logging.getLogger(__name__)


class BaseDepartmentAgent(ABC):
    name: str = "base_agent"
    department: str = "base"
    tools: List[BaseTool] = []

    def __init__(self):
        self._executor: AgentExecutor | None = None

    @abstractmethod
    def _get_system_prompt(self) -> str:
        """Return the system prompt describing this agent's role and capabilities."""
        ...

    async def execute(
        self,
        step: WorkflowStepState,
        context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        Execute a single workflow step.

        Returns a dict with:
          - output: the agent's output (string or structured)
          - success: bool
          - latency_ms: float
          - error: str | None
        """
        start = time.monotonic()
        try:
            result = await self._run_step(step, context or {})
            latency = (time.monotonic() - start) * 1000
            logger.info(
                f"[{self.name}] Step '{step['title']}' completed in {latency:.0f}ms"
            )
            return {
                "output": result,
                "success": True,
                "latency_ms": round(latency, 2),
                "error": None,
            }
        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            logger.error(f"[{self.name}] Step '{step['title']}' failed: {e}")
            return {
                "output": None,
                "success": False,
                "latency_ms": round(latency, 2),
                "error": str(e),
            }

    async def _run_step(
        self, step: WorkflowStepState, context: Dict[str, Any]
    ) -> Any:
        """
        Default implementation: single LLM call with the agent's system prompt.
        Subclasses with tool use can override this to invoke their AgentExecutor.
        """
        system_prompt = self._get_system_prompt()
        user_message = (
            f"Task: {step['title']}\n\n"
            f"Description: {step['description']}\n\n"
            f"Input data: {step['input_data']}\n\n"
            f"Additional context: {context}"
        )

        response = await acompletion(
            model=settings.ACTIVE_LLM,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=1024,
        )
        return response.choices[0].message.content
