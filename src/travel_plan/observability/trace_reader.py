"""Read-only views over the append-only workflow event trace."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class TraceReadError(ValueError):
    """Raised when an existing trace cannot be parsed safely."""


@dataclass(frozen=True)
class TraceEvent:
    """One normalized event, using reader terminology only.

    P1-A persists ``sequence`` and ``details``.  The reader exposes those values
    as ``event_id`` and ``payload`` without changing the file or its writer.
    """

    event_id: int
    trip_id: str
    plan_version: int
    parent_version: int | None
    event_type: str
    actor: str
    payload: dict[str, Any]
    trigger_review_number: int | None
    timestamp: str = ""


@dataclass(frozen=True)
class TimelineEntry:
    """A presentation-ready, deterministic description of a trace event."""

    event_id: int
    plan_version: int
    event_type: str
    actor: str
    description: str


class TraceReader:
    """Parse traces and create timelines without invoking workflow services."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def read(self, trip_id: str, plan_version: int | None = None) -> list[TraceEvent]:
        """Return events in append order.

        A missing trace represents a trip with no observed events.  Corrupt
        lines are reported rather than silently producing a misleading view.
        """

        path = self.root / trip_id / "events.jsonl"
        if not path.exists():
            return []

        events: list[TraceEvent] = []
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                    events.append(self._parse_event(raw, trip_id))
                except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                    raise TraceReadError(f"invalid event at {path}:{line_number}: {exc}") from exc
        return [event for event in events
                if plan_version is None or event.plan_version == plan_version]

    def timeline(self, trip_id: str, plan_version: int | None = None) -> list[TimelineEntry]:
        """Build an explainable timeline from the trip's recorded facts."""

        return [
            TimelineEntry(
                event_id=event.event_id,
                plan_version=event.plan_version,
                event_type=event.event_type,
                actor=event.actor,
                description=self._describe(event),
            )
            for event in self.read(trip_id, plan_version)
        ]

    def workflow_projection(self, trip_id: str, plan_version: int) -> dict[str, Any]:
        """Rebuild a version's graph solely from persisted trace facts."""
        from dataclasses import asdict
        from travel_plan.web.server import _stream_event
        from travel_plan.web.workflow_visualization import workflow_graph

        events = []
        for event in self.read(trip_id, plan_version):
            raw = asdict(event)
            raw["sequence"] = raw.pop("event_id")
            raw["details"] = raw.pop("payload")
            raw.pop("trigger_review_number", None)
            events.append(_stream_event(raw))
        return workflow_graph(events)

    def planning_story_projection(self, trip_id: str, plan_version: int) -> list[dict[str, Any]]:
        """Rebuild one version's story solely from persisted trace facts."""
        from dataclasses import asdict
        from travel_plan.web.planning_story import planning_story
        from travel_plan.web.server import _stream_event

        events = []
        for event in self.read(trip_id, plan_version):
            raw = asdict(event)
            raw["sequence"] = raw.pop("event_id")
            raw["details"] = raw.pop("payload")
            events.append(_stream_event(raw))
        return planning_story(events)

    def render(self, trip_id: str) -> str:
        """Render the timeline as stable, human-readable text."""

        return "\n".join(
            f"#{entry.event_id} v{entry.plan_version} "
            f"[{entry.event_type}] {entry.actor}: {entry.description}"
            for entry in self.timeline(trip_id)
        )

    @staticmethod
    def _parse_event(raw: Any, expected_trip_id: str) -> TraceEvent:
        if not isinstance(raw, dict):
            raise TypeError("event must be a JSON object")
        trip_id = raw["trip_id"]
        if trip_id != expected_trip_id:
            raise ValueError(f"trip_id {trip_id!r} does not match {expected_trip_id!r}")

        # Accept the persisted P1-A names and the terminology documented for
        # the reader.  This is compatibility at the read boundary only.
        event_id = raw.get("event_id", raw.get("sequence"))
        payload = raw.get("payload", raw.get("details", {}))
        if not isinstance(event_id, int) or isinstance(event_id, bool):
            raise TypeError("event_id/sequence must be an integer")
        if not isinstance(payload, dict):
            raise TypeError("payload/details must be an object")

        trigger = raw.get("trigger_review_number", payload.get("trigger_review_number"))
        return TraceEvent(
            event_id=event_id,
            trip_id=trip_id,
            plan_version=raw["plan_version"],
            parent_version=raw["parent_version"],
            event_type=raw["event_type"],
            actor=raw["actor"],
            payload=payload,
            trigger_review_number=trigger,
            timestamp=str(raw.get("timestamp", "")),
        )

    @staticmethod
    def _describe(event: TraceEvent) -> str:
        if not event.payload:
            return "completed"
        facts = ", ".join(
            f"{key}={json.dumps(value, ensure_ascii=False, sort_keys=True)}"
            for key, value in sorted(event.payload.items())
        )
        return facts
