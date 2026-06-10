from __future__ import annotations

from typing import cast

import anthropic
from anthropic.types import (
    TextBlockParam,
    ToolResultBlockParam,
    ToolUseBlockParam,
)

from incident_copilot.config import Settings
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

_ContentBlock = TextBlockParam | ToolUseBlockParam | ToolResultBlockParam


class AnthropicProvider:
    def __init__(self, settings: Settings) -> None:
        self._client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key.get_secret_value(),
            max_retries=3,
        )
        self._model = settings.llm_model

    @property
    def model(self) -> str:
        return self._model

    def complete(
        self,
        *,
        messages: list[Message],
        system: str,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        response = self._client.messages.create(
            model=self._model,
            system=system,
            messages=self._to_anthropic_messages(messages),
            max_tokens=max_tokens,
        )
        return self._parse_response(response)

    def tool_use(
        self,
        *,
        messages: list[Message],
        system: str,
        tools: list[ToolDefinition],
        max_tokens: int = 4096,
    ) -> LLMResponse:
        response = self._client.messages.create(
            model=self._model,
            system=system,
            messages=self._to_anthropic_messages(messages),
            tools=[
                {"name": t.name, "description": t.description, "input_schema": t.input_schema}
                for t in tools
            ],
            max_tokens=max_tokens,
        )
        return self._parse_response(response)

    def _to_anthropic_messages(self, messages: list[Message]) -> list[anthropic.types.MessageParam]:
        result: list[anthropic.types.MessageParam] = []
        i = 0
        while i < len(messages):
            msg = messages[i]
            if isinstance(msg, UserMessage):
                result.append({"role": "user", "content": msg.content})
                i += 1
            elif isinstance(msg, AssistantMessage):
                blocks: list[_ContentBlock] = []
                if msg.content is not None:
                    blocks.append(TextBlockParam(type="text", text=msg.content))
                for tc in msg.tool_calls:
                    blocks.append(
                        ToolUseBlockParam(type="tool_use", id=tc.id, name=tc.name, input=tc.input)
                    )
                result.append(
                    cast(anthropic.types.MessageParam, {"role": "assistant", "content": blocks})
                )
                i += 1
            elif isinstance(msg, ToolResultMessage):
                tool_results: list[ToolResultBlockParam] = []
                while i < len(messages) and isinstance(messages[i], ToolResultMessage):
                    tr = messages[i]
                    assert isinstance(tr, ToolResultMessage)
                    tool_results.append(
                        ToolResultBlockParam(
                            type="tool_result",
                            tool_use_id=tr.tool_call_id,
                            content=tr.content,
                        )
                    )
                    i += 1
                result.append(
                    cast(anthropic.types.MessageParam, {"role": "user", "content": tool_results})
                )
        return result

    def _parse_response(self, response: anthropic.types.Message) -> LLMResponse:
        text_content: str | None = None
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if isinstance(block, anthropic.types.TextBlock):
                text_content = block.text
            elif isinstance(block, anthropic.types.ToolUseBlock):
                tool_calls.append(ToolCall(id=block.id, name=block.name, input=block.input))

        return LLMResponse(
            content=text_content,
            tool_calls=tool_calls,
            stop_reason=response.stop_reason or "unknown",
            usage=TokenUsage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            ),
        )
