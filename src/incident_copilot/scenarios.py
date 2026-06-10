from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class ContainerSpec(BaseModel):
    name: str
    image: str
    ready: bool


class PodSpec(BaseModel):
    name: str
    namespace: str
    status: str
    restart_count: int = 0
    labels: dict[str, str] = {}
    containers: list[ContainerSpec]


class EventSpec(BaseModel):
    kind: str
    name: str
    namespace: str
    reason: str
    message: str
    count: int = 1


class MetricSample(BaseModel):
    timestamp: str
    value: float


class AlertSpec(BaseModel):
    name: str
    severity: str
    labels: dict[str, str] = {}
    annotations: dict[str, str] = {}


class RunbookStep(BaseModel):
    action: str
    description: str


class RunbookSpec(BaseModel):
    name: str
    trigger: str
    root_cause: str
    steps: list[RunbookStep]


class TrajectoryStep(BaseModel):
    agent: str
    tool: str
    args: dict[str, object] = {}


class Scenario(BaseModel):
    name: str
    description: str
    pods: list[PodSpec]
    logs: dict[str, list[str]]
    events: list[EventSpec]
    metrics: dict[str, list[MetricSample]]
    alerts: list[AlertSpec]
    runbooks: list[RunbookSpec]
    gold_trajectory: list[TrajectoryStep]

    @classmethod
    def load(cls, path: Path) -> Scenario:
        return cls.model_validate_json(path.read_text())
