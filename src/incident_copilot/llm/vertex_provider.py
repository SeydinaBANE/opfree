"""GCP Vertex AI provider stub — implement when LLM_PROVIDER=vertex is needed.

To activate: set LLM_PROVIDER=vertex, GOOGLE_CLOUD_PROJECT, and GOOGLE_CLOUD_REGION in .env,
then replace the NotImplementedError bodies with google-cloud-aiplatform + Anthropic on Vertex
calls.
"""

from __future__ import annotations

from incident_copilot.config import Settings
from incident_copilot.llm.base import LLMResponse, Message, ToolDefinition


class VertexProvider:
    def __init__(self, settings: Settings) -> None:
        self._model = settings.llm_model
        self._project = settings.google_cloud_project
        self._region = settings.google_cloud_region

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
        raise NotImplementedError("VertexProvider is a documented stub; see module docstring.")

    def tool_use(
        self,
        *,
        messages: list[Message],
        system: str,
        tools: list[ToolDefinition],
        max_tokens: int = 4096,
    ) -> LLMResponse:
        raise NotImplementedError("VertexProvider is a documented stub; see module docstring.")
