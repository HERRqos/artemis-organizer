"""LLM adapter.

The rest of the engine talks in (messages, tools) and gets back either
text or tool calls. Swapping providers means writing a second class
here, not touching conversation.py.
"""
from dataclasses import dataclass
from typing import Any, Protocol

import anthropic


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class LLMReply:
    text: str
    tool_calls: list[ToolCall]
    raw_content: list[Any]        # provider-native, appended back to history

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


class LLM(Protocol):
    def complete(self, system: str, messages: list[dict], tools: list[dict]) -> LLMReply: ...


class AnthropicLLM:
    def __init__(self, api_key: str, model: str, max_tokens: int = 1024):
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, system: str, messages: list[dict], tools: list[dict]) -> LLMReply:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            tools=tools,
            messages=messages,
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        calls = [
            ToolCall(id=b.id, name=b.name, arguments=b.input)
            for b in resp.content
            if b.type == "tool_use"
        ]
        # content blocks are dumped so they can be JSON-stored in the session
        return LLMReply(
            text=text,
            tool_calls=calls,
            raw_content=[b.model_dump() for b in resp.content],
        )
