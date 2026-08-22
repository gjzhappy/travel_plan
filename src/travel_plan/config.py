from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Config:
    agent_runtime_mode: str = "auto"
    data_mode: str = "offline"
    external_provider_mode: str = "mock"
    qdrant_top_k: int = 24
    daily_start_time: str = "08:30"
    daily_latest_end_time: str = "21:30"
    lunch_window: tuple[str, str] = ("11:30", "13:30")
    dinner_window: tuple[str, str] = ("17:30", "20:00")
    max_pois_per_day: int = 4
    hotel_change_min_gain: int = 60
    review_max_retries: int = 2
    transport_mode: str = "public_transit"
    mock_mode: bool = True
    mock_reference_date: str = "2026-01-01"
    mock_retrieved_at: str = "2026-01-01T00:00:00Z"
    state_dir: str = "data/state"
    route_candidate_limit: int = 6


DEFAULT_CONFIG = Config()


def load_config(path: str | Path | None = None, **overrides: Any) -> Config:
    """Load the deliberately small demo config without requiring a YAML package."""
    values: dict[str, Any] = {}
    if path is not None and Path(path).is_file():
        for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            key, raw_value = (part.strip() for part in line.split(":", 1))
            if key in {"agent_runtime_mode", "data_mode", "external_provider_mode"}:
                values[key] = raw_value.strip("\"'")
    values.update({key: value for key, value in overrides.items() if value is not None})
    config = Config(**values)
    if config.agent_runtime_mode not in {"auto", "opencode", "deterministic"}:
        raise ValueError("agent_runtime_mode must be auto, opencode, or deterministic")
    if config.data_mode != "offline":
        raise ValueError("data_mode is fixed to offline for this demo")
    if config.external_provider_mode != "mock":
        raise ValueError("external_provider_mode is fixed to mock for this demo")
    return config
