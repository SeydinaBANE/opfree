"""MCP client helper for agents.

Wraps ClientSession to provide typed list_tools() and call_tool() methods.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent

from incident_copilot.llm.base import ToolDefinition

_MCP_CALL_TIMEOUT = 30.0


class ToolCallError(Exception):
    pass


class MCPClient:
    def __init__(self, session: ClientSession) -> None:
        self._session = session

    async def list_tools(self) -> list[ToolDefinition]:
        result = await self._session.list_tools()
        return [
            ToolDefinition(
                name=tool.name,
                description=tool.description or "",
                input_schema=dict(tool.inputSchema),
            )
            for tool in result.tools
        ]

    async def call_tool(self, name: str, arguments: dict[str, object]) -> str:
        result = await asyncio.wait_for(
            self._session.call_tool(name, arguments),
            timeout=_MCP_CALL_TIMEOUT,
        )
        texts = [block.text for block in result.content if isinstance(block, TextContent)]
        content = "\n".join(texts)
        if result.isError:
            raise ToolCallError(f"Tool '{name}' returned error: {content}")
        return content


@asynccontextmanager
async def connect_to_server(command: str, args: list[str]) -> AsyncIterator[MCPClient]:
    params = StdioServerParameters(command=command, args=args)
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        yield MCPClient(session)
