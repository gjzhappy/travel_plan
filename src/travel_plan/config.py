from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
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
    state_dir: str = "data/state"


DEFAULT_CONFIG = Config()

