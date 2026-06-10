"""Kubernetes mock MCP server.

Serves k8s data from a scenario JSON file over stdio MCP.
Run standalone: uv run python -m incident_copilot.mcp_servers.k8s_mock --scenario crashloop
"""

from __future__ import annotations

import argparse
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from incident_copilot.scenarios import PodSpec, Scenario


class _K8sTools:
    def __init__(self, scenario: Scenario) -> None:
        self._scenario = scenario

    def list_pods(self, namespace: str | None = None) -> list[dict[str, object]]:
        pods: list[PodSpec] = self._scenario.pods
        if namespace is not None:
            pods = [p for p in pods if p.namespace == namespace]
        return [p.model_dump() for p in pods]

    def describe_pod(self, pod_name: str) -> dict[str, object]:
        for pod in self._scenario.pods:
            if pod.name == pod_name:
                return pod.model_dump()
        return {"error": f"pod '{pod_name}' not found"}

    def get_pod_logs(self, pod_name: str, tail_lines: int = 100) -> list[str]:
        lines = self._scenario.logs.get(pod_name, [])
        return lines[-tail_lines:]

    def get_events(
        self,
        namespace: str | None = None,
        involved_object: str | None = None,
    ) -> list[dict[str, object]]:
        events = self._scenario.events
        if namespace is not None:
            events = [e for e in events if e.namespace == namespace]
        if involved_object is not None:
            events = [e for e in events if e.name == involved_object]
        return [e.model_dump() for e in events]


def build_server(scenario: Scenario) -> FastMCP:
    tools = _K8sTools(scenario)
    server = FastMCP("k8s_mock")

    @server.tool()
    def list_pods(namespace: str | None = None) -> list[dict[str, object]]:
        """List pods, optionally filtered by namespace."""
        return tools.list_pods(namespace)

    @server.tool()
    def describe_pod(pod_name: str) -> dict[str, object]:
        """Describe a pod by name."""
        return tools.describe_pod(pod_name)

    @server.tool()
    def get_pod_logs(pod_name: str, tail_lines: int = 100) -> list[str]:
        """Get recent log lines for a pod."""
        return tools.get_pod_logs(pod_name, tail_lines)

    @server.tool()
    def get_events(
        namespace: str | None = None,
        involved_object: str | None = None,
    ) -> list[dict[str, object]]:
        """Get Kubernetes events, optionally filtered by namespace or involved object name."""
        return tools.get_events(namespace, involved_object)

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
    parser = argparse.ArgumentParser(description="k8s mock MCP server")
    parser.add_argument("--scenario", required=True, help="Scenario name or path to JSON")
    args = parser.parse_args()
    scenario = Scenario.load(_resolve_scenario_path(args.scenario))
    build_server(scenario).run(transport="stdio")


if __name__ == "__main__":
    main()
