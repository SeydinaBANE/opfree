from unittest.mock import MagicMock, patch

import pytest
from anthropic.types import Message, TextBlock, ToolUseBlock, Usage

from incident_copilot.config import Settings
from incident_copilot.llm.anthropic_provider import AnthropicProvider
from incident_copilot.llm.base import (
    AssistantMessage,
    LLMResponse,
    TokenUsage,
    ToolCall,
    ToolDefinition,
    ToolResultMessage,
    UserMessage,
)
from incident_copilot.llm.bedrock_provider import BedrockProvider
from incident_copilot.llm.factory import make_provider
from incident_copilot.llm.vertex_provider import VertexProvider


def _settings(**overrides: object) -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        anthropic_api_key="sk-ant-test",
        **overrides,
    )


def _usage(input_tokens: int = 10, output_tokens: int = 5) -> Usage:
    return Usage(input_tokens=input_tokens, output_tokens=output_tokens)


def _message(content: list[TextBlock | ToolUseBlock], stop_reason: str) -> Message:
    return Message(
        id="msg_test",
        type="message",
        role="assistant",
        content=content,
        model="claude-sonnet-4-6",
        stop_reason=stop_reason,  # type: ignore[arg-type]
        stop_sequence=None,
        usage=_usage(),
    )


# --- Factory ---


def test_factory_returns_anthropic_provider() -> None:
    provider = make_provider(_settings(llm_provider="anthropic"))
    assert isinstance(provider, AnthropicProvider)


def test_factory_returns_bedrock_stub() -> None:
    provider = make_provider(_settings(llm_provider="bedrock"))
    assert isinstance(provider, BedrockProvider)


def test_factory_returns_vertex_stub() -> None:
    provider = make_provider(_settings(llm_provider="vertex"))
    assert isinstance(provider, VertexProvider)


# --- LLMResponse ---


def test_llm_response_has_tool_calls_true() -> None:
    response = LLMResponse(
        tool_calls=[ToolCall(id="1", name="test", input={})],
        stop_reason="tool_use",
        usage=TokenUsage(input_tokens=10, output_tokens=5),
    )
    assert response.has_tool_calls is True


def test_llm_response_has_tool_calls_false() -> None:
    response = LLMResponse(
        content="hello",
        stop_reason="end_turn",
        usage=TokenUsage(input_tokens=10, output_tokens=5),
    )
    assert response.has_tool_calls is False


# --- AnthropicProvider ---


@patch("incident_copilot.llm.anthropic_provider.anthropic.Anthropic")
def test_anthropic_provider_complete_text(mock_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_cls.return_value = mock_client
    mock_client.messages.create.return_value = _message(
        content=[TextBlock(type="text", text="diagnosis complete", citations=None)],
        stop_reason="end_turn",
    )

    provider = AnthropicProvider(_settings())
    result = provider.complete(
        messages=[UserMessage(content="diagnose this")],
        system="You are an SRE copilot.",
    )

    assert result.content == "diagnosis complete"
    assert result.stop_reason == "end_turn"
    assert result.has_tool_calls is False
    assert result.usage.input_tokens == 10


@patch("incident_copilot.llm.anthropic_provider.anthropic.Anthropic")
def test_anthropic_provider_tool_use_returns_tool_calls(mock_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_cls.return_value = mock_client
    mock_client.messages.create.return_value = _message(
        content=[
            ToolUseBlock(
                type="tool_use",
                id="toolu_01",
                name="get_pod_logs",
                input={"pod_name": "frontend-abc"},
                caller=None,  # type: ignore[arg-type]
            )
        ],
        stop_reason="tool_use",
    )

    provider = AnthropicProvider(_settings())
    result = provider.tool_use(
        messages=[UserMessage(content="check the logs")],
        system="You are a log analyst.",
        tools=[
            ToolDefinition(
                name="get_pod_logs",
                description="Get pod logs",
                input_schema={
                    "type": "object",
                    "properties": {"pod_name": {"type": "string"}},
                    "required": ["pod_name"],
                },
            )
        ],
    )

    assert result.has_tool_calls is True
    assert result.tool_calls[0].name == "get_pod_logs"
    assert result.tool_calls[0].id == "toolu_01"
    assert result.tool_calls[0].input == {"pod_name": "frontend-abc"}
    assert result.stop_reason == "tool_use"


@patch("incident_copilot.llm.anthropic_provider.anthropic.Anthropic")
def test_anthropic_provider_passes_all_message_types(mock_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_cls.return_value = mock_client
    mock_client.messages.create.return_value = _message(
        content=[TextBlock(type="text", text="done", citations=None)],
        stop_reason="end_turn",
    )

    messages = [
        UserMessage(content="check the pod"),
        AssistantMessage(tool_calls=[ToolCall(id="tc1", name="get_pod_logs", input={"pod": "x"})]),
        ToolResultMessage(tool_call_id="tc1", content="log output here"),
    ]

    provider = AnthropicProvider(_settings())
    provider.complete(messages=messages, system="sys")

    _, kwargs = mock_client.messages.create.call_args
    sdk_messages = kwargs["messages"]
    assert len(sdk_messages) == 3
    assert sdk_messages[0]["role"] == "user"
    assert sdk_messages[1]["role"] == "assistant"
    assert sdk_messages[2]["role"] == "user"


# --- Stub providers ---


def test_bedrock_provider_raises_not_implemented() -> None:
    provider = BedrockProvider(_settings(llm_provider="bedrock"))
    with pytest.raises(NotImplementedError):
        provider.complete(messages=[UserMessage(content="x")], system="s")


def test_vertex_provider_raises_not_implemented() -> None:
    provider = VertexProvider(_settings(llm_provider="vertex"))
    with pytest.raises(NotImplementedError):
        provider.complete(messages=[UserMessage(content="x")], system="s")
