"""Runbook mock MCP server.

Serves runbook data from a scenario JSON file over stdio MCP.
Run standalone: uv run python -m incident_copilot.mcp_servers.runbook_mock --scenario crashloop
"""

from __future__ import annotations

import argparse
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from incident_copilot.scenarios import RunbookSpec, Scenario


class _RunbookTools:
    def __init__(self, scenario: Scenario) -> None:
        self._scenario = scenario

    def get_runbook(self, trigger: str) -> dict[str, object]:
        for rb in self._scenario.runbooks:
            if rb.trigger == trigger:
                return rb.model_dump()
        return {"error": f"No runbook found for trigger '{trigger}'"}

    def list_runbooks(self) -> list[dict[str, object]]:
        return [{"name": rb.name, "trigger": rb.trigger} for rb in self._scenario.runbooks]

    def list_runbook_steps(self, runbook_name: str) -> list[dict[str, object]]:
        runbooks: list[RunbookSpec] = self._scenario.runbooks
        for rb in runbooks:
            if rb.name == runbook_name:
                return [s.model_dump() for s in rb.steps]
        return [{"error": f"Runbook '{runbook_name}' not found"}]


def build_server(scenario: Scenario) -> FastMCP:
    tools = _RunbookTools(scenario)
    server = FastMCP("runbook_mock")

    @server.tool()
    def get_runbook(trigger: str) -> dict[str, object]:
        """Get a runbook by its alert trigger name."""
        return tools.get_runbook(trigger)

    @server.tool()
    def list_runbooks() -> list[dict[str, object]]:
        """List all available runbooks."""
        return tools.list_runbooks()

    @server.tool()
    def list_runbook_steps(runbook_name: str) -> list[dict[str, object]]:
        """List the remediation steps for a named runbook."""
        return tools.list_runbook_steps(runbook_name)

    return server


def _resolve_scenario_path(name_or_path: str) -> Path:
    path = Path(name_or_path)
    if path.exists():
        return path
    candidate = Path("scenarios") / f"{name_or_path}.json"
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"Scenario not found: '{name_or_path}'")


def main() -> None:
    parser = argparse.ArgumentParser(description="Runbook mock MCP server")
    parser.add_argument("--scenario", required=True, help="Scenario name or path to JSON")
    args = parser.parse_args()
    scenario = Scenario.load(_resolve_scenario_path(args.scenario))
    build_server(scenario).run(transport="stdio")


if __name__ == "__main__":
    main()
