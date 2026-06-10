"""Prometheus mock MCP server.

Serves metrics and alert data from a scenario JSON file over stdio MCP.
Run standalone: uv run python -m incident_copilot.mcp_servers.prometheus_mock --scenario crashloop
"""

from __future__ import annotations

import argparse
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from incident_copilot.scenarios import AlertSpec, MetricSample, Scenario


class _PrometheusTools:
    def __init__(self, scenario: Scenario) -> None:
        self._scenario = scenario

    def query_range(
        self,
        metric: str,
        _start: str | None = None,
        _end: str | None = None,
        step: str = "1m",
    ) -> dict[str, object]:
        samples: list[MetricSample] = self._scenario.metrics.get(metric, [])
        return {
            "metric": metric,
            "step": step,
            "values": [[s.timestamp, s.value] for s in samples],
        }

    def get_alerts(self, severity: str | None = None) -> list[dict[str, object]]:
        alerts: list[AlertSpec] = self._scenario.alerts
        if severity is not None:
            alerts = [a for a in alerts if a.severity == severity]
        return [a.model_dump() for a in alerts]

    def get_targets(self) -> list[dict[str, object]]:
        return [
            {
                "pod": pod.name,
                "namespace": pod.namespace,
                "status": "up" if pod.status == "Running" else "down",
            }
            for pod in self._scenario.pods
        ]


def build_server(scenario: Scenario) -> FastMCP:
    tools = _PrometheusTools(scenario)
    server = FastMCP("prometheus_mock")

    @server.tool()
    def query_range(
        metric: str,
        start: str | None = None,
        end: str | None = None,
        step: str = "1m",
    ) -> dict[str, object]:
        """Query a metric time series for a given range."""
        return tools.query_range(metric, start, end, step)

    @server.tool()
    def get_alerts(severity: str | None = None) -> list[dict[str, object]]:
        """Get currently firing alerts, optionally filtered by severity."""
        return tools.get_alerts(severity)

    @server.tool()
    def get_targets() -> list[dict[str, object]]:
        """Get scrape targets and their up/down status."""
        return tools.get_targets()

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
    parser = argparse.ArgumentParser(description="Prometheus mock MCP server")
    parser.add_argument("--scenario", required=True, help="Scenario name or path to JSON")
    args = parser.parse_args()
    scenario = Scenario.load(_resolve_scenario_path(args.scenario))
    build_server(scenario).run(transport="stdio")


if __name__ == "__main__":
    main()
