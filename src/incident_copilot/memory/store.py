from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

import structlog

log = structlog.get_logger()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    id          TEXT PRIMARY KEY,
    scenario_name TEXT NOT NULL,
    description TEXT NOT NULL,
    diagnosis   TEXT NOT NULL,
    findings_summary TEXT NOT NULL,
    resolved_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS preferences (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class IncidentRecord:
    id: str
    scenario_name: str
    description: str
    diagnosis: str
    findings_summary: str
    resolved_at: str

    @staticmethod
    def new(
        scenario_name: str,
        description: str,
        diagnosis: str,
        findings_summary: str,
    ) -> IncidentRecord:
        return IncidentRecord(
            id=str(uuid.uuid4()),
            scenario_name=scenario_name,
            description=description,
            diagnosis=diagnosis,
            findings_summary=findings_summary,
            resolved_at=datetime.now(UTC).isoformat(),
        )


class MemoryStore:
    def __init__(self, db_path: Path | str = ":memory:") -> None:
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def save_incident(self, record: IncidentRecord) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO incidents
                (id, scenario_name, description, diagnosis, findings_summary, resolved_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.scenario_name,
                record.description,
                record.diagnosis,
                record.findings_summary,
                record.resolved_at,
            ),
        )
        self._conn.commit()
        log.debug("incident_saved", id=record.id, scenario=record.scenario_name)

    def find_similar(self, scenario_name: str, *, limit: int = 3) -> list[IncidentRecord]:
        cursor = self._conn.execute(
            """
            SELECT id, scenario_name, description, diagnosis, findings_summary, resolved_at
            FROM incidents
            WHERE scenario_name = ?
            ORDER BY resolved_at DESC
            LIMIT ?
            """,
            (scenario_name, limit),
        )
        return [IncidentRecord(*row) for row in cursor.fetchall()]

    def get_preference(self, key: str) -> str | None:
        cursor = self._conn.execute("SELECT value FROM preferences WHERE key = ?", (key,))
        row = cursor.fetchone()
        return str(row[0]) if row else None

    def set_preference(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO preferences (key, value) VALUES (?, ?)",
            (key, value),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> MemoryStore:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()
