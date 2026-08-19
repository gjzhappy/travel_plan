from dataclasses import dataclass, field
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Evidence:
    source: str
    retrieved_at: str = field(default_factory=now_iso)
    kind: str = "fact"

