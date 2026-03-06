"""Base agent backed by LiteLLM — supports Anthropic, OpenAI, Gemini, Ollama, etc."""
from __future__ import annotations

import json
import logging
from typing import Any

import litellm

from event_agent.config.settings import get_settings

logger = logging.getLogger(__name__)

# Suppress LiteLLM's verbose logging unless debug is needed
litellm.suppress_debug_info = True


def _llm_kwargs() -> dict:
    """Extra kwargs forwarded to every litellm.acompletion call."""
    settings = get_settings()
    kwargs: dict[str, Any] = {}
    if settings.llm_api_key:
        kwargs["api_key"] = settings.llm_api_key
    if settings.llm_api_base:
        kwargs["api_base"] = settings.llm_api_base
    return kwargs


class BaseAgent:
    """Thin wrapper around LiteLLM that provides a simple completion + tool-use loop."""

    def __init__(self, system_prompt: str):
        settings = get_settings()
        self._model = settings.llm_model
        self._system = system_prompt

    async def run(self, user_message: str, max_tokens: int = 4096) -> str:
        """Single-turn completion (no tools)."""
        response = await litellm.acompletion(
            model=self._model,
            messages=[
                {"role": "system", "content": self._system},
                {"role": "user", "content": user_message},
            ],
            max_tokens=max_tokens,
            **_llm_kwargs(),
        )
        return response.choices[0].message.content or ""

    async def run_with_tools(
        self,
        user_message: str,
        tools: list[dict],
        tool_handler: dict[str, Any],
        max_iterations: int = 10,
    ) -> str:
        """
        Tool-use loop (OpenAI function-calling format, supported by LiteLLM for all providers).

        tools: list of {"type": "function", "function": {"name", "description", "parameters"}}
        tool_handler: mapping of tool_name -> async callable(args_dict) -> str
        """
        messages: list[dict] = [
            {"role": "system", "content": self._system},
            {"role": "user", "content": user_message},
        ]

        for _ in range(max_iterations):
            response = await litellm.acompletion(
                model=self._model,
                messages=messages,
                tools=tools,
                max_tokens=4096,
                **_llm_kwargs(),
            )
            choice = response.choices[0]
            msg = choice.message

            if choice.finish_reason == "stop":
                return msg.content or ""

            if choice.finish_reason == "tool_calls" and msg.tool_calls:
                # Append assistant turn (must be serialisable)
                messages.append(msg.model_dump(exclude_none=True))

                for tool_call in msg.tool_calls:
                    handler = tool_handler.get(tool_call.function.name)
                    try:
                        args = json.loads(tool_call.function.arguments or "{}")
                        result = await handler(args) if handler else f"Unknown tool: {tool_call.function.name}"
                    except Exception as exc:
                        result = f"Error: {exc}"

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(result),
                    })
            else:
                return msg.content or ""

        return msg.content or ""
