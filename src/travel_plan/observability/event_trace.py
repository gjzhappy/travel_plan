import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("travel_plan.event_trace")


@dataclass(frozen=True)
class WorkflowEvent:
    """A stable, minimal description of one workflow decision or hand-off."""

    sequence: int
    trip_id: str
    plan_version: int
    parent_version: int | None
    event_type: str
    actor: str
    details: dict[str, Any] = field(default_factory=dict)


class EventTrace:
    """Append-only JSONL trace whose failures never escape into the workflow."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def record(
        self,
        trip_id: str,
        plan_version: int,
        parent_version: int | None,
        event_type: str,
        actor: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        try:
            path = self.root / trip_id / "events.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            sequence = self._next_sequence(path)
            event = WorkflowEvent(
                sequence, trip_id, plan_version, parent_version, event_type, actor, details or {}
            )
            with path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(asdict(event), ensure_ascii=False, sort_keys=True) + "\n")
        except Exception as exc:  # Event tracing is deliberately outside the business gate.
            log.warning("workflow event could not be written: %s", exc)

    @staticmethod
    def _next_sequence(path: Path) -> int:
        if not path.exists():
            return 1
        with path.open(encoding="utf-8") as stream:
            return sum(1 for line in stream if line.strip()) + 1
