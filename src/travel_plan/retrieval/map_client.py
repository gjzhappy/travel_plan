from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
from typing import Protocol

@dataclass(frozen=True)
class Location:
    name: str; lat: float; lon: float

@dataclass(frozen=True)
class RouteResult:
    duration_min: int; distance_km: float; mode: str; source: str; retrieved_at: str

class MapClient(Protocol):
    def route(self, origin: Location, destination: Location, mode: str) -> RouteResult: ...
    def search_nearby(self, location: Location, keyword: str, radius_km: float) -> list[Location]: ...

class MockMapClient:
    def __init__(self, overrides: dict[tuple[str,str], int] | None = None, retrieved_at: str = "2026-01-01T00:00:00Z"):
        self.overrides=overrides or {}; self.calls=0; self.retrieved_at=retrieved_at
    def route(self, origin: Location, destination: Location, mode: str="public_transit") -> RouteResult:
        self.calls += 1
        key=(origin.name,destination.name)
        lat1,lon1,lat2,lon2=map(radians,(origin.lat,origin.lon,destination.lat,destination.lon))
        a=sin((lat2-lat1)/2)**2+cos(lat1)*cos(lat2)*sin((lon2-lon1)/2)**2
        distance=6371*2*asin(sqrt(a)); speed={"walking":4.5,"public_transit":22,"driving":30}.get(mode,22)
        duration=self.overrides.get(key, max(5, round(distance/speed*60+6)))
        return RouteResult(duration,round(distance,2),mode,"mock_map",self.retrieved_at)
    def search_nearby(self, location: Location, keyword: str, radius_km: float) -> list[Location]: return []

class RealMapClient:
    def __init__(self, api_key: str): self.api_key=api_key
    def route(self, origin: Location, destination: Location, mode: str) -> RouteResult:
        raise RuntimeError("Real map provider adapter requires a configured deployment endpoint")
    def search_nearby(self, location: Location, keyword: str, radius_km: float) -> list[Location]:
        raise RuntimeError("Real map provider adapter requires a configured deployment endpoint")
