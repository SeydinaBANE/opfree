from __future__ import annotations

from incident_copilot.llm.base import Message

_MIN_EFFECTIVE_MAX = 2


def evict(
    messages: list[Message],
    *,
    max_messages: int = 20,
) -> tuple[list[Message], list[Message]]:
    if len(messages) <= max_messages:
        return messages, []

    effective_max = max(max_messages, _MIN_EFFECTIVE_MAX)
    tail_count = effective_max - 1
    split = len(messages) - tail_count

    head = messages[:1]
    evicted = messages[1:split]
    tail = messages[split:]
    return head + tail, evicted
