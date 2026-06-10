"""AWS Bedrock provider stub — implement when LLM_PROVIDER=bedrock is needed.

To activate: set LLM_PROVIDER=bedrock, AWS_REGION, and AWS_PROFILE in .env,
then replace the NotImplementedError bodies with boto3 + anthropic.AnthropicBedrock calls.
"""

from __future__ import annotations

from incident_copilot.config import Settings
from incident_copilot.llm.base import LLMResponse, Message, ToolDefinition


class BedrockProvider:
    def __init__(self, settings: Settings) -> None:
        self._model = settings.llm_model
        self._region = settings.aws_region

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
        raise NotImplementedError("BedrockProvider is a documented stub; see module docstring.")

    def tool_use(
        self,
        *,
        messages: list[Message],
        system: str,
        tools: list[ToolDefinition],
        max_tokens: int = 4096,
    ) -> LLMResponse:
        raise NotImplementedError("BedrockProvider is a documented stub; see module docstring.")
