from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any
from travel_plan.errors import RequirementError


@dataclass
class Party:
    adult: int = 1
    child: int = 0


@dataclass
class Requirement:
    city: str = "上海"
    days: int = 3
    start_date: str = field(default_factory=lambda: date.today().isoformat())
    party: Party = field(default_factory=Party)
    interests: list[str] = field(default_factory=list)
    pace: str = "moderate"
    transport: str = "public_transit"
    walking: str = "medium"
    must_visit: list[str] = field(default_factory=list)
    rejected_pois: list[str] = field(default_factory=list)
    rejected_categories: list[str] = field(default_factory=list)
    food_preferences: list[str] = field(default_factory=list)
    include_meals: bool = True
    lodging_strategy: str = "fixed"
    max_hotel_changes: int = 0
    budget: float = 5000
    retrieval_query: str = ""
    has_luggage: bool = True

    def __post_init__(self) -> None:
        errors = []
        if self.days <= 0 or self.days > 30: errors.append("days must be between 1 and 30")
        if self.budget < 0: errors.append("budget must be >= 0")
        if self.max_hotel_changes < 0: errors.append("max_hotel_changes must be >= 0")
        if self.pace not in {"relaxed", "moderate", "intensive"}: errors.append("invalid pace")
        if self.transport not in {"public_transit", "driving", "walking"}: errors.append("invalid transport")
        if self.walking not in {"low", "medium", "high"}: errors.append("invalid walking")
        if self.lodging_strategy not in {"fixed", "flexible"}: errors.append("invalid lodging_strategy")
        try: date.fromisoformat(self.start_date)
        except ValueError: errors.append("start_date must be ISO date")
        if self.party.adult < 0 or self.party.child < 0 or self.party.adult + self.party.child < 1: errors.append("invalid party")
        if errors: raise RequirementError("; ".join(errors))

    def to_dict(self) -> dict[str, Any]: return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Requirement":
        data = dict(value); data["party"] = Party(**data.get("party", {})); return cls(**data)

