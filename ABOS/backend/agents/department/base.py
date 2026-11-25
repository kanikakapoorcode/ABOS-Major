"""
Base class for all ABOS department agents.

Each department agent:
- Has a name, department, and list of LangChain tools
- Exposes registered tools to the LLM through bounded function calling
- Exposes a single async execute() method that the graph calls

To add a new department agent, subclass BaseDepartmentAgent,
set name/department/tools, and implement _get_system_prompt().
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from langchain_core.tools import BaseTool
from litellm import acompletion

from backend.agents.state import WorkflowStepState
from backend.core.config import settings

logger = logging.getLogger(__name__)

MAX_TOOL_CALL_ROUNDS = 3


class BaseDepartmentAgent(ABC):
    name: str = "base_agent"
    department: str = "base"
    tools: List[BaseTool] = []

    def __init__(self):
        pass

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
        Default implementation: LLM response with bounded tool execution.

        The LLM receives the task description, prior step output, and this
        agent's registered tools. Tool execution is sequential and bounded.

        Returns the final LLM response content.
        """
        system_prompt = self._get_system_prompt()

        # Format prior step outputs for context injection
        prior_outputs = ""
        if context.get("completed_steps"):
            prior_outputs = "\n\nPrior step outputs (use as input context):\n"
            for s in context["completed_steps"]:
                output = s.get("output")
                if isinstance(output, dict):
                    output = json.dumps(output, indent=2)
                prior_outputs += f"- {s['title']}: {str(output)[:500]}\n"

        user_message = (
            f"Task: {step['title']}\n\n"
            f"Description: {step['description']}\n\n"
            f"Input data: {json.dumps(step['input_data'], indent=2)}"
            f"{prior_outputs}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        tool_by_name = {registered_tool.name: registered_tool for registered_tool in self.tools}
        tool_definitions = []
        for registered_tool in self.tools:
            args_schema = registered_tool.args_schema
            parameters = (
                args_schema.model_json_schema()
                if args_schema is not None
                else {"type": "object", "properties": {}}
            )
            tool_definitions.append(
                {
                    "type": "function",
                    "function": {
                        "name": registered_tool.name,
                        "description": registered_tool.description,
                        "parameters": parameters,
                    },
                }
            )

        for round_index in range(MAX_TOOL_CALL_ROUNDS + 1):
            # On the final synthesis round (no more tool calls expected),
            # use a higher token limit so the response isn't truncated.
            is_final_round = round_index == MAX_TOOL_CALL_ROUNDS
            request = {
                "model": settings.ACTIVE_LLM,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 512 if is_final_round else 256,
            }
            if tool_definitions:
                request["tools"] = tool_definitions
                request["tool_choice"] = "auto"

            response = await acompletion(**request)
            message = response.choices[0].message
            tool_calls = getattr(message, "tool_calls", None) or []

            if not tool_calls:
                if message.content is None:
                    raise ValueError("Agent returned neither a response nor a tool call.")
                return message.content

            if round_index == MAX_TOOL_CALL_ROUNDS:
                raise RuntimeError(
                    f"Agent exceeded the {MAX_TOOL_CALL_ROUNDS}-round tool execution limit."
                )

            assistant_tool_message = {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [],
            }
            for tool_call in tool_calls:
                function = tool_call.function
                if not tool_call.id:
                    raise ValueError(
                        f"Agent returned a tool call without an ID for '{function.name}'."
                    )
                assistant_tool_message["tool_calls"].append(
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": function.name,
                            "arguments": function.arguments,
                        },
                    }
                )
            messages.append(assistant_tool_message)

            for tool_call in tool_calls:
                function = tool_call.function
                registered_tool = tool_by_name.get(function.name)
                if registered_tool is None:
                    raise ValueError(f"Agent requested unregistered tool '{function.name}'.")

                try:
                    arguments = json.loads(function.arguments)
                except (TypeError, json.JSONDecodeError) as exc:
                    raise ValueError(
                        f"Agent returned invalid JSON arguments for tool '{function.name}'."
                    ) from exc

                if not isinstance(arguments, dict):
                    raise ValueError(
                        f"Agent returned non-object arguments for tool '{function.name}'."
                    )

                tool_result = await registered_tool.ainvoke(arguments)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function.name,
                        "content": json.dumps(tool_result, ensure_ascii=False, default=str),
                    }
                )

        raise RuntimeError("Agent ended without producing a response.")
