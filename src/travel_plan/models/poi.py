from dataclasses import dataclass, field
from typing import Any


@dataclass
class POI:
    poi_id: int; name: str; city: str; district: str; lat: float; lon: float
    category: str; ticket_price: float; duration_min: int; reservation_required: bool
    opening_hours: dict[str, Any]; semantic_description: str = ""; outdoor: bool = False
    similarity: float = 0.0; priority: float = 0.0; score_reasons: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list); description: str = ""
    special_dates: dict[str, Any] = field(default_factory=dict); latest_entry_time: str | None = None
    ticket_required: bool = False; family_friendly_score: int = 0; night_view_score: int = 0
    indoor: bool = False; crowd_level: str = "medium"


@dataclass
class Restaurant:
    restaurant_id: int; name: str; cuisine: str; district: str; lat: float; lon: float
    price_per_person: float; opening_hours: dict[str, Any]


@dataclass
class Hotel:
    hotel_id: int; name: str; district: str; lat: float; lon: float; nightly_price: float
    luggage_storage: bool = True
