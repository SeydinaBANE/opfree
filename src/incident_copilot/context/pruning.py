from __future__ import annotations

from incident_copilot.context import summarizer, window
from incident_copilot.llm.base import LLMProvider, Message


def prune(
    messages: list[Message],
    llm: LLMProvider,
    *,
    max_messages: int = 20,
) -> list[Message]:
    kept, evicted = window.evict(messages, max_messages=max_messages)
    if not evicted:
        return messages
    summary_msg = summarizer.summarize(evicted, llm)
    return [kept[0], summary_msg, *kept[1:]]
