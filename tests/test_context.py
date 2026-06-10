from __future__ import annotations

from incident_copilot.context import pruning, summarizer, window
from incident_copilot.llm.base import (
    AssistantMessage,
    LLMResponse,
    Message,
    TokenUsage,
    ToolCall,
    ToolDefinition,
    ToolResultMessage,
    UserMessage,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _user(text: str = "msg") -> UserMessage:
    return UserMessage(content=text)


def _assistant_tool(tool_name: str = "list_pods") -> AssistantMessage:
    return AssistantMessage(
        tool_calls=[ToolCall(id="tc1", name=tool_name, input={"ns": "default"})]
    )


def _result(content: str = "ok") -> ToolResultMessage:
    return ToolResultMessage(tool_call_id="tc1", content=content)


def _make_messages(n_rounds: int) -> list[Message]:
    msgs: list[Message] = [_user("investigate")]
    for i in range(n_rounds):
        msgs.append(_assistant_tool(f"tool_{i}"))
        msgs.append(_result(f"result_{i}"))
    return msgs


class _FixedLLM:
    @property
    def model(self) -> str:
        return "fixed"

    def complete(
        self,
        *,
        messages: list[Message],  # noqa: ARG002
        system: str,  # noqa: ARG002
        max_tokens: int = 1024,  # noqa: ARG002
    ) -> LLMResponse:
        return LLMResponse(
            content="Summary of prior tool interactions.",
            stop_reason="end_turn",
            usage=TokenUsage(input_tokens=20, output_tokens=10),
        )

    def tool_use(
        self,
        *,
        messages: list[Message],  # noqa: ARG002
        system: str,  # noqa: ARG002
        tools: list[ToolDefinition],  # noqa: ARG002
        max_tokens: int = 4096,  # noqa: ARG002
    ) -> LLMResponse:
        raise AssertionError("tool_use not expected in context tests")


# ---------------------------------------------------------------------------
# Window tests
# ---------------------------------------------------------------------------


def test_window_no_eviction_under_limit() -> None:
    msgs = _make_messages(3)  # 7 messages
    kept, evicted = window.evict(msgs, max_messages=10)
    assert kept == msgs
    assert evicted == []


def test_window_evicts_middle_messages() -> None:
    msgs = _make_messages(5)  # 11 messages: 1 head + 10 body
    kept, evicted = window.evict(msgs, max_messages=5)
    assert len(kept) == 5
    assert len(evicted) == 6
    assert kept[0] == msgs[0]  # head preserved
    assert kept[-1] == msgs[-1]  # tail preserved


def test_window_always_keeps_first_message() -> None:
    msgs = _make_messages(10)  # 21 messages
    kept, _evicted = window.evict(msgs, max_messages=5)
    assert kept[0] == msgs[0]


def test_window_exact_limit_no_eviction() -> None:
    msgs = _make_messages(2)  # 5 messages
    kept, evicted = window.evict(msgs, max_messages=5)
    assert evicted == []
    assert kept == msgs


def test_window_one_over_evicts_one() -> None:
    msgs = _make_messages(2)  # 5 messages
    kept, evicted = window.evict(msgs, max_messages=4)
    assert len(kept) == 4
    assert len(evicted) == 1


def test_window_returns_correct_types() -> None:
    msgs = _make_messages(5)
    kept, evicted = window.evict(msgs, max_messages=5)
    assert all(isinstance(m, UserMessage | AssistantMessage | ToolResultMessage) for m in kept)
    assert all(isinstance(m, UserMessage | AssistantMessage | ToolResultMessage) for m in evicted)


# ---------------------------------------------------------------------------
# Summarizer tests
# ---------------------------------------------------------------------------


def test_summarizer_produces_user_message() -> None:
    evicted: list[Message] = [_assistant_tool(), _result("pod is crashing")]
    llm = _FixedLLM()
    result = summarizer.summarize(evicted, llm)
    assert isinstance(result, UserMessage)
    assert "[Prior context summary]" in result.content
    assert "Summary of prior tool interactions." in result.content


def test_summarizer_handles_empty_evicted() -> None:
    llm = _FixedLLM()
    result = summarizer.summarize([], llm)
    assert isinstance(result, UserMessage)
    assert "no interactions" in result.content.lower()


def test_summarizer_formats_tool_call() -> None:
    evicted: list[Message] = [_assistant_tool("describe_pod"), _result("Status: CrashLoopBackOff")]
    llm = _FixedLLM()
    summarizer.summarize(evicted, llm)


def test_summarizer_formats_assistant_text() -> None:
    msg = AssistantMessage(content="I found the issue.")
    llm = _FixedLLM()
    result = summarizer.summarize([msg], llm)
    assert isinstance(result, UserMessage)


# ---------------------------------------------------------------------------
# Pruning tests
# ---------------------------------------------------------------------------


def test_pruning_no_op_under_limit() -> None:
    msgs = _make_messages(3)
    llm = _FixedLLM()
    result = pruning.prune(msgs, llm, max_messages=20)
    assert result == msgs


def test_pruning_evicts_and_inserts_summary() -> None:
    msgs = _make_messages(5)  # 11 messages
    llm = _FixedLLM()
    result = pruning.prune(msgs, llm, max_messages=5)
    assert result[0] == msgs[0]
    assert isinstance(result[1], UserMessage)
    assert "[Prior context summary]" in result[1].content
    assert len(result) == 6  # head + summary + 4 tail


def test_pruning_preserves_head_and_tail() -> None:
    msgs = _make_messages(6)  # 13 messages
    llm = _FixedLLM()
    result = pruning.prune(msgs, llm, max_messages=5)
    assert result[0] == msgs[0]
    assert result[-1] == msgs[-1]


def test_pruning_result_length() -> None:
    msgs = _make_messages(10)  # 21 messages
    llm = _FixedLLM()
    result = pruning.prune(msgs, llm, max_messages=10)
    assert len(result) == 11  # head + summary + 9 tail
