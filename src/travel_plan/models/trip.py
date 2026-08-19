from dataclasses import asdict, dataclass, field
from typing import Any

NODE_TYPES = {"hotel_departure","hotel_checkout","luggage_drop","attraction","lunch","dinner","hotel_checkin","hotel_return"}

@dataclass
class Node:
    type: str; name: str; start_time: str; end_time: str
    poi_id: int | None = None; transport_mode: str | None = None
    distance_km: float = 0; duration_min: int = 0; cost: float = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    def __post_init__(self):
        if self.type not in NODE_TYPES: raise ValueError(f"invalid node type: {self.type}")

@dataclass
class DayPlan:
    day: int; date: str; theme: str; nodes: list[Node] = field(default_factory=list); route_score: float = 0

@dataclass
class HotelSegment:
    hotel_id: int; name: str; start_day: int; end_day: int; nightly_price: float

@dataclass
class Budget:
    tickets: float = 0; meals: float = 0; hotels: float = 0; transport: float = 0
    @property
    def total(self): return round(self.tickets+self.meals+self.hotels+self.transport, 2)

@dataclass
class TripPlan:
    trip_id: str; days: list[DayPlan]; hotels: list[HotelSegment]; budget: Budget
    hotel_decision: dict[str, Any] = field(default_factory=dict); evidence: list[dict[str, Any]] = field(default_factory=list)
    remaining_issues: list[dict[str, Any]] = field(default_factory=list); review_count: int = 0
    def to_dict(self):
        result=asdict(self); result["budget"]["total"]=self.budget.total; return result

