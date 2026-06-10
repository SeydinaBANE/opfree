from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel


class ToolCall(BaseModel):
    id: str
    name: str
    input: dict[str, object]


class TokenUsage(BaseModel):
    input_tokens: int
    output_tokens: int


class LLMResponse(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCall] = []
    stop_reason: str
    usage: TokenUsage

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class ToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: dict[str, object]


class UserMessage(BaseModel):
    role: Literal["user"] = "user"
    content: str


class AssistantMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str | None = None
    tool_calls: list[ToolCall] = []


class ToolResultMessage(BaseModel):
    tool_call_id: str
    content: str


type Message = UserMessage | AssistantMessage | ToolResultMessage


class LLMProvider(Protocol):
    @property
    def model(self) -> str: ...

    def complete(
        self,
        *,
        messages: list[Message],
        system: str,
        max_tokens: int = 1024,
    ) -> LLMResponse: ...

    def tool_use(
        self,
        *,
        messages: list[Message],
        system: str,
        tools: list[ToolDefinition],
        max_tokens: int = 4096,
    ) -> LLMResponse: ...
