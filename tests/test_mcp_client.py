from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.types import TextContent

from incident_copilot.mcp_servers.client import MCPClient, ToolCallError, connect_to_server


def _make_text_content(text: str) -> TextContent:
    return TextContent(type="text", text=text)


def _make_session(
    tools: list[MagicMock] | None = None,
    call_result_text: str = "result",
    is_error: bool = False,
) -> AsyncMock:
    session = AsyncMock()
    session.list_tools.return_value = MagicMock(tools=tools or [])
    call_result = MagicMock()
    call_result.content = [_make_text_content(call_result_text)]
    call_result.isError = is_error
    session.call_tool.return_value = call_result
    return session


def _make_tool(name: str, description: str = "") -> MagicMock:
    tool = MagicMock()
    tool.name = name
    tool.description = description
    tool.inputSchema = {"type": "object", "properties": {}}
    return tool


# --- list_tools ---


@pytest.mark.asyncio
async def test_list_tools_returns_tool_definitions() -> None:
    session = _make_session(tools=[_make_tool("list_pods", "List pods")])
    client = MCPClient(session)

    tools = await client.list_tools()

    assert len(tools) == 1
    assert tools[0].name == "list_pods"
    assert tools[0].description == "List pods"
    assert tools[0].input_schema == {"type": "object", "properties": {}}


@pytest.mark.asyncio
async def test_list_tools_none_description_becomes_empty_string() -> None:
    tool = _make_tool("my_tool")
    tool.description = None
    session = _make_session(tools=[tool])
    client = MCPClient(session)

    tools = await client.list_tools()

    assert tools[0].description == ""


@pytest.mark.asyncio
async def test_list_tools_empty_server() -> None:
    session = _make_session(tools=[])
    client = MCPClient(session)

    tools = await client.list_tools()

    assert tools == []


# --- call_tool ---


@pytest.mark.asyncio
async def test_call_tool_returns_text_content() -> None:
    session = _make_session(call_result_text="pod logs here")
    client = MCPClient(session)

    result = await client.call_tool("get_pod_logs", {"pod_name": "my-pod"})

    assert result == "pod logs here"
    session.call_tool.assert_called_once_with("get_pod_logs", {"pod_name": "my-pod"})


@pytest.mark.asyncio
async def test_call_tool_error_raises_tool_call_error() -> None:
    session = _make_session(call_result_text="unknown tool: foo", is_error=True)
    client = MCPClient(session)

    with pytest.raises(ToolCallError, match="returned error"):
        await client.call_tool("foo", {})


@pytest.mark.asyncio
async def test_call_tool_joins_multiple_text_blocks() -> None:
    session = AsyncMock()
    call_result = MagicMock()
    call_result.isError = False
    call_result.content = [
        _make_text_content("line 1"),
        _make_text_content("line 2"),
    ]
    session.call_tool.return_value = call_result
    client = MCPClient(session)

    result = await client.call_tool("some_tool", {})

    assert result == "line 1\nline 2"


# --- connect_to_server ---


async def test_connect_to_server_yields_mcp_client() -> None:
    mock_session = AsyncMock()
    mock_session.initialize = AsyncMock()

    @asynccontextmanager
    async def fake_stdio(
        *_args: object, **_kwargs: object
    ) -> AsyncIterator[tuple[AsyncMock, AsyncMock]]:
        yield (AsyncMock(), AsyncMock())

    @asynccontextmanager
    async def fake_client_session(*_args: object, **_kwargs: object) -> AsyncIterator[AsyncMock]:
        yield mock_session

    with (
        patch("incident_copilot.mcp_servers.client.stdio_client", fake_stdio),
        patch("incident_copilot.mcp_servers.client.ClientSession", fake_client_session),
    ):
        async with connect_to_server("python", ["-m", "test"]) as client:
            assert isinstance(client, MCPClient)
        mock_session.initialize.assert_awaited_once()
