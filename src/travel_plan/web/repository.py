"""Small, thread-safe lifecycle store for plans exposed by the web demo."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Any


@dataclass(frozen=True)
class PlanRecord:
    plan_id: str
    version: int
    created_at: str
    updated_at: str
    request: dict[str, Any]
    state: dict[str, Any]
    display_result: dict[str, Any]
    events: list[dict[str, Any]]
    review: dict[str, Any]
    explainability: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(asdict(self))


class PlanRepository:
    """Keep immutable version snapshots in memory; workflow state remains authoritative."""

    def __init__(self):
        self._plans: dict[str, list[PlanRecord]] = {}
        self._lock = RLock()

    def save(
        self,
        plan_id: str,
        version: int,
        request: dict[str, Any],
        state: dict[str, Any],
        display_result: dict[str, Any],
        events: list[dict[str, Any]],
        review: dict[str, Any],
        explainability: dict[str, Any],
    ) -> PlanRecord:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            versions = self._plans.setdefault(plan_id, [])
            if versions and version <= versions[-1].version:
                raise ValueError("计划版本必须递增")
            created_at = versions[0].created_at if versions else now
            record = PlanRecord(
                plan_id, version, created_at, now, deepcopy(request), deepcopy(state),
                deepcopy(display_result), deepcopy(events), deepcopy(review),
                deepcopy(explainability),
            )
            versions.append(record)
            return deepcopy(record)

    def current(self, plan_id: str) -> PlanRecord | None:
        with self._lock:
            versions = self._plans.get(plan_id, [])
            return deepcopy(versions[-1]) if versions else None

    def versions(self, plan_id: str) -> list[PlanRecord]:
        with self._lock:
            return deepcopy(self._plans.get(plan_id, []))
