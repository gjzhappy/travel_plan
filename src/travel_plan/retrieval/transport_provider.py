"""Deterministic transport costs for route planning.

The mock provider deliberately caches only common tourist corridors.  Every other
pair is derived from coordinates, so the fixture stays intentionally small.
"""

from dataclasses import dataclass
import json
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class TransportResult:
    mode: str
    duration_min: int
    distance_km: float
    walking_minutes: int
    transfer_count: int
    source: str
    retrieved_at: str = "2026-01-01T00:00:00Z"


class TransportProvider(Protocol):
    def route(self, from_poi, to_poi, preference=None) -> TransportResult: ...


def haversine_km(origin, destination) -> float:
    lat1, lon1, lat2, lon2 = map(
        radians, (origin.lat, origin.lon, destination.lat, destination.lon)
    )
    value = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin(
        (lon2 - lon1) / 2
    ) ** 2
    return 6371 * 2 * asin(sqrt(value))


class HierarchicalMockTransportProvider:
    """Popular-route lookup followed by a deterministic geographic estimate."""

    def __init__(self, cache_path: Path | None = None, retrieved_at="2026-01-01T00:00:00Z"):
        default = Path(__file__).parents[3] / "data/mock/shanghai_transport_routes.json"
        routes = json.loads((cache_path or default).read_text(encoding="utf-8"))
        self._routes = {
            frozenset((item["from"], item["to"])): item for item in routes
        }
        self.retrieved_at = retrieved_at

    def route(self, from_poi, to_poi, preference=None) -> TransportResult:
        distance = round(haversine_km(from_poi, to_poi), 2)
        cached = self._routes.get(frozenset((from_poi.name, to_poi.name)))
        if cached:
            option = self._select(cached["options"], preference)
            return TransportResult(
                option["mode"], option["duration_min"],
                option.get("distance_km", distance), option["walking_minutes"],
                option["transfer_count"], "mock_cache", self.retrieved_at,
            )
        return self._estimate(distance, preference)

    @staticmethod
    def _mode(preference) -> str:
        value = preference.get("mode") if isinstance(preference, dict) else preference
        return {"public_transit": "metro", "driving": "taxi", "walking": "walk"}.get(
            value, value or "metro"
        )

    def _select(self, options, preference):
        mode = self._mode(preference)
        return next((option for option in options if option["mode"] == mode), options[0])

    def _estimate(self, distance: float, preference) -> TransportResult:
        requested = self._mode(preference)
        # Walking is available only for a genuinely short hop. Otherwise a request
        # for walking falls back to metro, rather than inventing an impractical leg.
        mode = "walk" if distance < 1.5 and requested == "walk" else requested
        if mode == "walk" and distance >= 1.5:
            mode = "metro"
        if mode == "walk":
            duration = max(1, round(distance / 4 * 60))
            walking, transfers = duration, 0
        elif mode == "taxi":
            duration = max(6, round(distance / 30 * 60 + 6))
            walking, transfers = 0, 0
        else:
            mode = "metro"
            transfers = 0 if distance <= 6 else 1
            # 22 km/h is a conservative network speed; the six-minute fixed
            # buffer covers platform access and the occasional transfer.
            duration = max(5, round(distance / 22 * 60 + 6))
            walking = 6
        return TransportResult(
            mode, duration, distance, walking, transfers, "rule_estimate", self.retrieved_at
        )
