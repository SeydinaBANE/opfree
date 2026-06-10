from incident_copilot.config import Settings
from incident_copilot.llm.anthropic_provider import AnthropicProvider
from incident_copilot.llm.base import LLMProvider
from incident_copilot.llm.bedrock_provider import BedrockProvider
from incident_copilot.llm.vertex_provider import VertexProvider


def make_provider(settings: Settings) -> LLMProvider:
    match settings.llm_provider:
        case "anthropic":
            return AnthropicProvider(settings)
        case "bedrock":
            return BedrockProvider(settings)
        case "vertex":
            return VertexProvider(settings)
        case _:
            raise AssertionError(f"Unhandled provider: {settings.llm_provider}")
