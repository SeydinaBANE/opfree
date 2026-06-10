from __future__ import annotations

import structlog

from incident_copilot.llm.base import ToolCall, ToolDefinition

log = structlog.get_logger()


def validate(tool_call: ToolCall, available_tools: list[ToolDefinition]) -> str | None:
    tool_map = {t.name: t for t in available_tools}

    if tool_call.name not in tool_map:
        available = ", ".join(sorted(tool_map.keys()))
        log.warning("hallucinated_tool", tool=tool_call.name, available=available)
        return (
            f"Tool `{tool_call.name}` does not exist. "
            f"Available tools: {available}. Please choose one of the listed tools."
        )

    schema = tool_map[tool_call.name].input_schema
    raw_required = schema.get("required")
    required: list[str] = [str(f) for f in raw_required] if isinstance(raw_required, list) else []

    missing = [f for f in required if f not in tool_call.input]
    if missing:
        log.warning("missing_required_args", tool=tool_call.name, missing=missing)
        return (
            f"Tool `{tool_call.name}` missing required arguments: {missing}. "
            f"Please provide all required arguments."
        )

    return None
