from dataclasses import dataclass
from typing import Protocol

from travel_plan.retrieval.transport_provider import (
    HierarchicalMockTransportProvider,
    TransportResult,
)

@dataclass(frozen=True)
class Location:
    name: str; lat: float; lon: float

RouteResult = TransportResult

class MapClient(Protocol):
    def route(self, origin: Location, destination: Location, mode: str) -> RouteResult: ...
    def search_nearby(self, location: Location, keyword: str, radius_km: float) -> list[Location]: ...

class MockMapClient:
    """Compatibility facade for map consumers that also need nearby search."""
    def __init__(self, overrides: dict[tuple[str,str], int] | None = None, retrieved_at: str = "2026-01-01T00:00:00Z", transport=None):
        self.overrides=overrides or {}; self.calls=0
        self.transport=transport or HierarchicalMockTransportProvider(retrieved_at=retrieved_at)
    def route(self, origin: Location, destination: Location, mode: str="public_transit") -> RouteResult:
        self.calls += 1
        key=(origin.name,destination.name)
        result=self.transport.route(origin,destination,mode)
        if key not in self.overrides:return result
        return TransportResult(result.mode,self.overrides[key],result.distance_km,result.walking_minutes,result.transfer_count,result.source,result.retrieved_at)
    def search_nearby(self, location: Location, keyword: str, radius_km: float) -> list[Location]: return []

class RealMapClient:
    def __init__(self, api_key: str): self.api_key=api_key
    def route(self, origin: Location, destination: Location, mode: str) -> RouteResult:
        raise RuntimeError("Real map provider adapter requires a configured deployment endpoint")
    def search_nearby(self, location: Location, keyword: str, radius_km: float) -> list[Location]:
        raise RuntimeError("Real map provider adapter requires a configured deployment endpoint")
