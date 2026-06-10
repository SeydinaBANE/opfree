from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from incident_copilot.mcp_servers.k8s_mock import _K8sTools
from incident_copilot.mcp_servers.k8s_mock import _resolve_scenario_path as k8s_resolve
from incident_copilot.mcp_servers.k8s_mock import build_server as k8s_build_server
from incident_copilot.mcp_servers.k8s_mock import main as k8s_main
from incident_copilot.mcp_servers.prometheus_mock import _PrometheusTools
from incident_copilot.mcp_servers.prometheus_mock import _resolve_scenario_path as prom_resolve
from incident_copilot.mcp_servers.prometheus_mock import build_server as prom_build_server
from incident_copilot.mcp_servers.prometheus_mock import main as prom_main
from incident_copilot.mcp_servers.runbook_mock import _resolve_scenario_path as runbook_resolve
from incident_copilot.mcp_servers.runbook_mock import _RunbookTools
from incident_copilot.mcp_servers.runbook_mock import build_server as runbook_build_server
from incident_copilot.mcp_servers.runbook_mock import main as runbook_main
from incident_copilot.scenarios import Scenario

SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"


@pytest.fixture(params=["crashloop", "oom", "latency_spike"])
def scenario(request: pytest.FixtureRequest) -> Scenario:
    return Scenario.load(SCENARIOS_DIR / f"{request.param}.json")


# --- Schema validation ---


def test_all_scenarios_load_and_validate(scenario: Scenario) -> None:
    assert scenario.name in {"crashloop", "oom", "latency_spike"}
    assert len(scenario.pods) > 0
    assert len(scenario.gold_trajectory) > 0


def test_scenario_invalid_json_raises() -> None:
    with pytest.raises((ValidationError, ValueError)):
        Scenario.model_validate_json('{"name": "bad"}')


def test_crashloop_scenario_structure() -> None:
    s = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    assert s.name == "crashloop"
    assert any(p.status == "CrashLoopBackOff" for p in s.pods)
    assert any(a.name == "KubePodCrashLooping" for a in s.alerts)
    assert len(s.runbooks) > 0


def test_oom_scenario_structure() -> None:
    s = Scenario.load(SCENARIOS_DIR / "oom.json")
    assert s.name == "oom"
    assert any(p.status == "OOMKilled" for p in s.pods)
    assert "container_memory_usage_bytes" in s.metrics


def test_latency_spike_scenario_structure() -> None:
    s = Scenario.load(SCENARIOS_DIR / "latency_spike.json")
    assert s.name == "latency_spike"
    assert all(p.status == "Running" for p in s.pods)
    assert "http_request_duration_seconds_p99" in s.metrics


# --- k8s tool outputs ---


def test_k8s_list_pods_all(scenario: Scenario) -> None:
    tools = _K8sTools(scenario)
    pods = tools.list_pods()
    assert len(pods) == len(scenario.pods)
    assert all("name" in p and "status" in p for p in pods)


def test_k8s_list_pods_namespace_filter() -> None:
    s = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    tools = _K8sTools(s)
    pods = tools.list_pods(namespace="production")
    assert all(p["namespace"] == "production" for p in pods)
    assert len(pods) < len(s.pods)


def test_k8s_describe_pod_found() -> None:
    s = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    tools = _K8sTools(s)
    result = tools.describe_pod("payment-service-7d9f8c-xkj2p")
    assert result["name"] == "payment-service-7d9f8c-xkj2p"
    assert result["status"] == "CrashLoopBackOff"


def test_k8s_describe_pod_not_found() -> None:
    s = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    tools = _K8sTools(s)
    result = tools.describe_pod("nonexistent-pod")
    assert "error" in result


def test_k8s_get_pod_logs_returns_lines() -> None:
    s = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    tools = _K8sTools(s)
    lines = tools.get_pod_logs("payment-service-7d9f8c-xkj2p")
    assert len(lines) > 0
    assert any("connection refused" in line for line in lines)


def test_k8s_get_pod_logs_tail_lines() -> None:
    s = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    tools = _K8sTools(s)
    lines = tools.get_pod_logs("payment-service-7d9f8c-xkj2p", tail_lines=2)
    assert len(lines) <= 2


def test_k8s_get_pod_logs_unknown_pod() -> None:
    s = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    tools = _K8sTools(s)
    assert tools.get_pod_logs("no-such-pod") == []


def test_k8s_get_events_all() -> None:
    s = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    tools = _K8sTools(s)
    events = tools.get_events()
    assert len(events) == len(s.events)


def test_k8s_get_events_namespace_filter() -> None:
    s = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    tools = _K8sTools(s)
    events = tools.get_events(namespace="production")
    assert all(e["namespace"] == "production" for e in events)


def test_k8s_get_events_object_filter() -> None:
    s = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    tools = _K8sTools(s)
    events = tools.get_events(involved_object="payment-service-7d9f8c-xkj2p")
    assert all(e["name"] == "payment-service-7d9f8c-xkj2p" for e in events)


# --- Prometheus tool outputs ---


def test_prometheus_query_range_known_metric() -> None:
    s = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    tools = _PrometheusTools(s)
    result = tools.query_range("kube_pod_container_status_restarts_total")
    assert result["metric"] == "kube_pod_container_status_restarts_total"
    values = result["values"]
    assert isinstance(values, list)
    assert len(values) > 0


def test_prometheus_query_range_unknown_metric() -> None:
    s = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    tools = _PrometheusTools(s)
    result = tools.query_range("nonexistent_metric")
    assert result["values"] == []


def test_prometheus_get_alerts_all() -> None:
    s = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    tools = _PrometheusTools(s)
    alerts = tools.get_alerts()
    assert len(alerts) == len(s.alerts)
    assert all("name" in a and "severity" in a for a in alerts)


def test_prometheus_get_alerts_severity_filter() -> None:
    s = Scenario.load(SCENARIOS_DIR / "oom.json")
    tools = _PrometheusTools(s)
    warnings = tools.get_alerts(severity="warning")
    assert all(a["severity"] == "warning" for a in warnings)


def test_prometheus_get_targets() -> None:
    s = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    tools = _PrometheusTools(s)
    targets = tools.get_targets()
    assert len(targets) == len(s.pods)
    assert all("pod" in t and "status" in t for t in targets)


# --- Runbook tool outputs ---


def test_runbook_get_runbook_found() -> None:
    s = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    tools = _RunbookTools(s)
    rb = tools.get_runbook("KubePodCrashLooping")
    assert rb["name"] == "pod-crashloop-db-connection"
    assert "steps" in rb


def test_runbook_get_runbook_not_found() -> None:
    s = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    tools = _RunbookTools(s)
    result = tools.get_runbook("UnknownAlert")
    assert "error" in result


def test_runbook_list_runbooks() -> None:
    s = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    tools = _RunbookTools(s)
    runbooks = tools.list_runbooks()
    assert len(runbooks) == len(s.runbooks)
    assert all("name" in rb and "trigger" in rb for rb in runbooks)


def test_runbook_list_runbook_steps() -> None:
    s = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    tools = _RunbookTools(s)
    steps = tools.list_runbook_steps("pod-crashloop-db-connection")
    assert len(steps) > 0
    assert all("action" in step for step in steps)


def test_runbook_list_runbook_steps_not_found() -> None:
    s = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    tools = _RunbookTools(s)
    result = tools.list_runbook_steps("no-such-runbook")
    assert len(result) == 1
    assert "error" in result[0]


# --- _resolve_scenario_path ---


def test_k8s_resolve_path_by_direct_path() -> None:
    path = k8s_resolve(str(SCENARIOS_DIR / "crashloop.json"))
    assert path.name == "crashloop.json"


def test_k8s_resolve_path_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(SCENARIOS_DIR.parent)
    assert k8s_resolve("crashloop").name == "crashloop.json"


def test_k8s_resolve_path_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        k8s_resolve("nonexistent_scenario_xyzzy")


def test_prom_resolve_path_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(SCENARIOS_DIR.parent)
    assert prom_resolve("oom").name == "oom.json"


def test_prom_resolve_path_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        prom_resolve("nonexistent_scenario_xyzzy")


def test_runbook_resolve_path_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(SCENARIOS_DIR.parent)
    assert runbook_resolve("latency_spike").name == "latency_spike.json"


def test_runbook_resolve_path_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        runbook_resolve("nonexistent_scenario_xyzzy")


# --- build_server (exercises FastMCP-registered tool bodies) ---


async def test_k8s_build_server_all_tools() -> None:
    s = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    server = k8s_build_server(s)
    assert isinstance(server, FastMCP)

    _, r = await server.call_tool("list_pods", {})
    assert len(r["result"]) == len(s.pods)

    _, r = await server.call_tool("describe_pod", {"pod_name": "payment-service-7d9f8c-xkj2p"})
    assert r["name"] == "payment-service-7d9f8c-xkj2p"

    _, r = await server.call_tool("get_pod_logs", {"pod_name": "payment-service-7d9f8c-xkj2p"})
    assert len(r["result"]) > 0

    _, r = await server.call_tool("get_events", {})
    assert len(r["result"]) == len(s.events)


async def test_prom_build_server_all_tools() -> None:
    s = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    server = prom_build_server(s)
    assert isinstance(server, FastMCP)

    metric = "kube_pod_container_status_restarts_total"
    _, r = await server.call_tool("query_range", {"metric": metric})
    assert r["metric"] == metric

    _, r = await server.call_tool("get_alerts", {})
    assert len(r["result"]) == len(s.alerts)

    _, r = await server.call_tool("get_targets", {})
    assert len(r["result"]) == len(s.pods)


async def test_runbook_build_server_all_tools() -> None:
    s = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    server = runbook_build_server(s)
    assert isinstance(server, FastMCP)

    _, r = await server.call_tool("get_runbook", {"trigger": "KubePodCrashLooping"})
    assert r["name"] == "pod-crashloop-db-connection"

    _, r = await server.call_tool("list_runbooks", {})
    assert len(r["result"]) == len(s.runbooks)

    _, r = await server.call_tool(
        "list_runbook_steps", {"runbook_name": "pod-crashloop-db-connection"}
    )
    assert len(r["result"]) > 0


# --- main() ---


def test_k8s_main_runs() -> None:
    mock_args = MagicMock()
    mock_args.scenario = str(SCENARIOS_DIR / "crashloop.json")
    with (
        patch("argparse.ArgumentParser.parse_args", return_value=mock_args),
        patch.object(FastMCP, "run"),
    ):
        k8s_main()


def test_prom_main_runs() -> None:
    mock_args = MagicMock()
    mock_args.scenario = str(SCENARIOS_DIR / "crashloop.json")
    with (
        patch("argparse.ArgumentParser.parse_args", return_value=mock_args),
        patch.object(FastMCP, "run"),
    ):
        prom_main()


def test_runbook_main_runs() -> None:
    mock_args = MagicMock()
    mock_args.scenario = str(SCENARIOS_DIR / "crashloop.json")
    with (
        patch("argparse.ArgumentParser.parse_args", return_value=mock_args),
        patch.object(FastMCP, "run"),
    ):
        runbook_main()
