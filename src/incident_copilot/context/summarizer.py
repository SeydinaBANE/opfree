from __future__ import annotations

import json

from incident_copilot.llm.base import (
    AssistantMessage,
    LLMProvider,
    Message,
    ToolResultMessage,
    UserMessage,
)

_SYSTEM = (
    "Summarize the following tool interactions in 2-3 sentences. "
    "Focus on what was discovered, not on the mechanics of the calls."
)
_MAX_CONTENT_CHARS = 200


def _format(messages: list[Message]) -> str:
    lines: list[str] = []
    for msg in messages:
        if isinstance(msg, AssistantMessage):
            for tc in msg.tool_calls:
                args = json.dumps(tc.input)[:80]
                lines.append(f"Called {tc.name}({args})")
            if msg.content:
                lines.append(f"Observed: {msg.content[:_MAX_CONTENT_CHARS]}")
        elif isinstance(msg, ToolResultMessage):
            content = msg.content
            if len(content) > _MAX_CONTENT_CHARS:
                content = content[:_MAX_CONTENT_CHARS] + "…"
            lines.append(f"Result: {content}")
        elif isinstance(msg, UserMessage):
            lines.append(f"Note: {msg.content[:_MAX_CONTENT_CHARS]}")
    return "\n".join(lines) if lines else "No tool interactions to summarize."


def summarize(evicted: list[Message], llm: LLMProvider) -> UserMessage:
    if not evicted:
        return UserMessage(content="[Prior context: no interactions to summarize.]")
    response = llm.complete(
        messages=[UserMessage(content=_format(evicted))],
        system=_SYSTEM,
        max_tokens=256,
    )
    return UserMessage(content=f"[Prior context summary]: {response.content or ''}")
