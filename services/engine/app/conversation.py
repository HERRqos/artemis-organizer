"""The tool-calling loop. This is the part worth reading twice.

  history + user message
      -> LLM
      -> if it asks for tools: run them, append results, ask again
      -> else: that text is the reply
"""
import logging

from assistant_shared.config import Settings

from .llm import LLM
from .prompts import HANDOFF_MESSAGE, build_system_prompt
from .tools import TOOL_SCHEMAS, ToolContext, dispatch

log = logging.getLogger("engine.conversation")

MAX_TOOL_ROUNDS = 5


class Conversation:
    def __init__(self, settings: Settings, llm: LLM, owner_name: str = "la psicóloga"):
        self._s = settings
        self._llm = llm
        self._owner = owner_name

    def run(self, user_text: str, history: list[dict], ctx: ToolContext) -> tuple[str, list[dict]]:
        """Returns (reply_text, new_history)."""
        system = build_system_prompt(self._s, self._owner)
        messages = history + [{"role": "user", "content": user_text}]

        for round_no in range(MAX_TOOL_ROUNDS):
            reply = self._llm.complete(system, messages, TOOL_SCHEMAS)
            messages.append({"role": "assistant", "content": reply.raw_content})

            if not reply.wants_tools:
                return reply.text, messages

            results = []
            for call in reply.tool_calls:
                log.info("tool=%s args=%s", call.name, call.arguments)
                output = dispatch(call.name, call.arguments, ctx)
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call.id,
                        "content": str(output),
                    }
                )
            messages.append({"role": "user", "content": results})

            if ctx.escalated:
                return HANDOFF_MESSAGE.format(owner=self._owner), messages

        log.warning("tool loop hit MAX_TOOL_ROUNDS for %s", ctx.sender)
        return HANDOFF_MESSAGE.format(owner=self._owner), messages
