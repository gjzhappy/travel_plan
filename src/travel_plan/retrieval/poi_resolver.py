"""Exact, deterministic resolution of user place expressions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
import unicodedata

from travel_plan.models.poi import POI


def normalize_poi_name(value: str) -> str:
    """Apply only Unicode width/case and whitespace normalization."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value).strip()).casefold()


@dataclass(frozen=True)
class POIResolution:
    source_text: str
    status: str
    poi_id: int | None = None
    canonical_name: str | None = None
    matched_by: str | None = None
    matched_value: str | None = None
    candidates: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class CanonicalPOIResolver:
    def __init__(self, pois: list[POI]):
        self.pois = pois

    def resolve(self, expression: str) -> POIResolution:
        checks = (
            ("canonical_name", lambda p: p.canonical_name == expression, lambda p: p.canonical_name),
            ("alias", lambda p: expression in p.aliases, lambda _p: expression),
            ("normalized_canonical_name", lambda p: normalize_poi_name(p.canonical_name) == normalize_poi_name(expression), lambda p: p.canonical_name),
            ("normalized_alias", lambda p: any(normalize_poi_name(a) == normalize_poi_name(expression) for a in p.aliases), lambda p: next(a for a in p.aliases if normalize_poi_name(a) == normalize_poi_name(expression))),
        )
        for matched_by, predicate, matched_value in checks:
            matches = [poi for poi in self.pois if predicate(poi)]
            if len(matches) == 1:
                poi = matches[0]
                return POIResolution(expression, "resolved", poi.poi_id, poi.canonical_name, matched_by, matched_value(poi))
            if len(matches) > 1:
                return POIResolution(expression, "ambiguous", candidates=[
                    {"poi_id": poi.poi_id, "canonical_name": poi.canonical_name} for poi in matches
                ])
        return POIResolution(expression, "unresolved")
