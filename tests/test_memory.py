from __future__ import annotations

import time
import uuid
from pathlib import Path
from unittest.mock import AsyncMock

from incident_copilot.agents.graph import build_graph
from incident_copilot.agents.state import GraphState
from incident_copilot.agents.supervisor import _build_prompt, _prior_context
from incident_copilot.llm.base import (
    LLMResponse,
    Message,
    TokenUsage,
    ToolDefinition,
)
from incident_copilot.mcp_servers.client import MCPClient
from incident_copilot.memory.store import IncidentRecord, MemoryStore
from incident_copilot.scenarios import Scenario

SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _record(
    scenario_name: str = "crashloop",
    diagnosis: str = "ROOT CAUSE: DB unreachable.",
) -> IncidentRecord:
    return IncidentRecord.new(
        scenario_name=scenario_name,
        description="Payment service crash-looping.",
        diagnosis=diagnosis,
        findings_summary="[log_analyst] connection refused",
    )


# ---------------------------------------------------------------------------
# MemoryStore — incidents
# ---------------------------------------------------------------------------


def test_store_save_and_retrieve() -> None:
    with MemoryStore() as store:
        record = _record()
        store.save_incident(record)
        found = store.find_similar("crashloop")
        assert len(found) == 1
        assert found[0].id == record.id
        assert found[0].diagnosis == record.diagnosis


def test_store_find_similar_filters_by_scenario_name() -> None:
    with MemoryStore() as store:
        store.save_incident(_record("crashloop"))
        store.save_incident(_record("oom"))
        assert len(store.find_similar("crashloop")) == 1
        assert len(store.find_similar("oom")) == 1
        assert len(store.find_similar("latency_spike")) == 0


def test_store_find_similar_returns_recent_first() -> None:
    with MemoryStore() as store:
        r1 = _record(diagnosis="Diagnosis A")
        time.sleep(0.01)
        r2 = _record(diagnosis="Diagnosis B")
        store.save_incident(r1)
        store.save_incident(r2)
        found = store.find_similar("crashloop")
        assert found[0].diagnosis == "Diagnosis B"


def test_store_find_similar_respects_limit() -> None:
    with MemoryStore() as store:
        for i in range(5):
            store.save_incident(_record(diagnosis=f"Diagnosis {i}"))
        assert len(store.find_similar("crashloop", limit=2)) == 2


def test_store_find_similar_returns_empty_for_unknown() -> None:
    with MemoryStore() as store:
        assert store.find_similar("unknown_scenario") == []


def test_store_replace_on_same_id() -> None:
    with MemoryStore() as store:
        r = _record()
        store.save_incident(r)
        updated = IncidentRecord(
            id=r.id,
            scenario_name=r.scenario_name,
            description=r.description,
            diagnosis="Updated diagnosis.",
            findings_summary=r.findings_summary,
            resolved_at=r.resolved_at,
        )
        store.save_incident(updated)
        found = store.find_similar("crashloop")
        assert len(found) == 1
        assert found[0].diagnosis == "Updated diagnosis."


# ---------------------------------------------------------------------------
# MemoryStore — preferences
# ---------------------------------------------------------------------------


def test_store_preference_round_trip() -> None:
    with MemoryStore() as store:
        store.set_preference("output_format", "json")
        assert store.get_preference("output_format") == "json"


def test_store_preference_missing_returns_none() -> None:
    with MemoryStore() as store:
        assert store.get_preference("nonexistent") is None


def test_store_preference_overwrite() -> None:
    with MemoryStore() as store:
        store.set_preference("key", "v1")
        store.set_preference("key", "v2")
        assert store.get_preference("key") == "v2"


# ---------------------------------------------------------------------------
# IncidentRecord factory
# ---------------------------------------------------------------------------


def test_incident_record_new_generates_uuid_and_timestamp() -> None:
    r = IncidentRecord.new(
        scenario_name="oom",
        description="OOM kill",
        diagnosis="ROOT CAUSE: memory leak.",
        findings_summary="[metrics_analyst] memory saturation",
    )
    assert len(r.id) == 36  # UUID format
    assert r.resolved_at.endswith("+00:00")
    assert r.scenario_name == "oom"


# ---------------------------------------------------------------------------
# Supervisor + memory integration
# ---------------------------------------------------------------------------


def test_supervisor_includes_prior_incidents_in_first_prompt() -> None:
    scenario = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    state = GraphState(
        scenario=scenario,
        findings=[],
        trajectory=[],
        input_tokens=0,
        output_tokens=0,
        iteration_count=0,
        next_agent="",
        diagnosis=None,
        start_time=time.monotonic(),
    )

    with MemoryStore() as store:
        store.save_incident(
            _record(scenario_name="crashloop", diagnosis="ROOT CAUSE: DB unreachable.")
        )
        prior = _prior_context(store, state)
        prompt = _build_prompt(state, prior)

    assert "ROOT CAUSE: DB unreachable." in prompt
    assert "Past diagnoses" in prompt


def test_supervisor_no_prior_context_when_store_empty() -> None:
    scenario = Scenario.load(SCENARIOS_DIR / "crashloop.json")
    state = GraphState(
        scenario=scenario,
        findings=[],
        trajectory=[],
        input_tokens=0,
        output_tokens=0,
        iteration_count=0,
        next_agent="",
        diagnosis=None,
        start_time=time.monotonic(),
    )

    with MemoryStore() as store:
        prior = _prior_context(store, state)
    prompt = _build_prompt(state, prior)

    assert "Past diagnoses" not in prompt


# ---------------------------------------------------------------------------
# Graph + persist node integration
# ---------------------------------------------------------------------------


async def test_graph_persist_node_writes_to_store() -> None:
    class ScriptedLLM:
        def __init__(self, responses: list[LLMResponse]) -> None:
            self._iter = iter(responses)

        @property
        def model(self) -> str:
            return "scripted"

        def complete(
            self,
            *,
            messages: list[Message],  # noqa: ARG002
            system: str,  # noqa: ARG002
            max_tokens: int = 1024,  # noqa: ARG002
        ) -> LLMResponse:
            return next(self._iter)

        def tool_use(
            self,
            *,
            messages: list[Message],  # noqa: ARG002
            system: str,  # noqa: ARG002
            tools: list[ToolDefinition],  # noqa: ARG002
            max_tokens: int = 4096,  # noqa: ARG002
        ) -> LLMResponse:
            return next(self._iter)

    usage = TokenUsage(input_tokens=10, output_tokens=10)
    llm = ScriptedLLM(
        [
            LLMResponse(content="log_analyst", stop_reason="end_turn", usage=usage),
            LLMResponse(content="DB connection refused.", stop_reason="end_turn", usage=usage),
            LLMResponse(content="synthesize", stop_reason="end_turn", usage=usage),
            LLMResponse(
                content=(
                    "ROOT CAUSE: DB unreachable.\n"
                    "EVIDENCE: connection refused.\n"
                    "REMEDIATION: restart pod.\n"
                    "CONFIDENCE: high"
                ),
                stop_reason="end_turn",
                usage=usage,
            ),
        ]
    )

    k8s_mcp = AsyncMock(spec=MCPClient)
    k8s_mcp.list_tools.return_value = []
    prom_mcp = AsyncMock(spec=MCPClient)
    prom_mcp.list_tools.return_value = []
    runbook_mcp = AsyncMock(spec=MCPClient)
    runbook_mcp.list_tools.return_value = []

    scenario = Scenario.load(SCENARIOS_DIR / "crashloop.json")

    with MemoryStore() as store:
        graph = build_graph(
            llm,
            store=store,
            k8s_client=k8s_mcp,
            prom_client=prom_mcp,
            runbook_client=runbook_mcp,
        )
        initial = GraphState(
            scenario=scenario,
            findings=[],
            trajectory=[],
            input_tokens=0,
            output_tokens=0,
            iteration_count=0,
            next_agent="",
            diagnosis=None,
            start_time=time.monotonic(),
        )
        await graph.ainvoke(initial, config={"configurable": {"thread_id": str(uuid.uuid4())}})
        saved = store.find_similar("crashloop")

    assert len(saved) == 1
    assert "ROOT CAUSE" in saved[0].diagnosis
