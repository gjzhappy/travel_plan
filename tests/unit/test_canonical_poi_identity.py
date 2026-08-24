from copy import deepcopy

import pytest

from travel_plan.agents.requirement_agent import preserve_user_intent
from travel_plan.errors import MustVisitResolutionError
from travel_plan.config import Config
from travel_plan.models.trip import DayPlan
from travel_plan.models.poi import POI
from travel_plan.models.requirement import Requirement
from travel_plan.planning.route_planner import RoutePlanner
from travel_plan.retrieval.poi_resolver import CanonicalPOIResolver
from travel_plan.retrieval.qdrant_repository import QdrantRepository
from travel_plan.retrieval.service import RetrievalService
from travel_plan.retrieval.weather_client import MockWeatherClient


HOURS = {"weekly_hours": {day: ["09:00", "20:00"] for day in
         ("mon", "tue", "wed", "thu", "fri", "sat", "sun")},
         "special_dates": {}, "latest_entry_time": "18:00"}


def poi(poi_id, canonical_name, aliases=()):
    return POI(poi_id, canonical_name, "上海", "测试", 31, 121, "乐园", 1, 60,
               False, HOURS, canonical_name=canonical_name, aliases=list(aliases))


class Facts:
    def __init__(self, pois): self.pois = pois
    def all_pois(self, city): return [p for p in self.pois if p.city == city]
    def get_pois(self, ids): return [p for p in self.pois if p.poi_id in ids]


def test_resolver_exact_canonical_alias_and_normalization():
    resolver = CanonicalPOIResolver([poi(1046, "上海迪士尼乐园", ["上海迪士尼", "上海Disney"])])
    exact = resolver.resolve("上海迪士尼乐园")
    alias = resolver.resolve("上海迪士尼")
    normalized = resolver.resolve("  上海ｄｉｓｎｅｙ  ")
    assert (exact.status, exact.poi_id, exact.matched_by) == ("resolved", 1046, "canonical_name")
    assert (alias.status, alias.poi_id, alias.matched_by) == ("resolved", 1046, "alias")
    assert (normalized.status, normalized.poi_id, normalized.matched_by) == ("resolved", 1046, "normalized_alias")


def test_resolver_unknown_and_ambiguous_fail_safe():
    resolver = CanonicalPOIResolver([poi(1, "甲公园", ["人民公园"]), poi(2, "乙公园", ["人民公园"])])
    assert resolver.resolve("不存在的测试景点ABC").status == "unresolved"
    result = resolver.resolve("人民公园")
    assert result.status == "ambiguous"
    assert {candidate["poi_id"] for candidate in result.candidates} == {1, 2}


def test_must_visit_is_injected_when_semantic_top_k_misses_and_deduplicated_when_hit():
    disney = poi(1046, "上海迪士尼乐园", ["上海迪士尼"])
    other = poi(1001, "外滩")
    facts = Facts([disney, other])
    weather = MockWeatherClient({})
    missed = RetrievalService(QdrantRepository([{"poi_id": 1001, "city": "上海", "semantic_description": "夜景"}]), facts, weather, 1)
    req = Requirement(must_visit=["上海迪士尼"], retrieval_query="夜景")
    candidates = missed.shortlist(req)
    assert [p.poi_id for p in candidates].count(1046) == 1
    assert req.resolved_must_visit[0]["source_text"] == "上海迪士尼"
    assert req.resolved_must_visit[0]["canonical_name"] == "上海迪士尼乐园"

    hit = RetrievalService(QdrantRepository([{"poi_id": 1046, "city": "上海", "semantic_description": "夜景"}]), facts, weather, 1)
    assert [p.poi_id for p in hit.shortlist(Requirement(must_visit=["上海迪士尼"]))].count(1046) == 1


def test_unresolved_and_ambiguous_must_visit_fail_closed():
    weather = MockWeatherClient({})
    with pytest.raises(MustVisitResolutionError, match="无法.*确认"):
        RetrievalService(QdrantRepository([]), Facts([]), weather).shortlist(
            Requirement(must_visit=["不存在的测试景点ABC"]))
    shared = [poi(1, "甲公园", ["人民公园"]), poi(2, "乙公园", ["人民公园"])]
    with pytest.raises(MustVisitResolutionError, match="多个匹配"):
        RetrievalService(QdrantRepository([]), Facts(shared), weather).shortlist(
            Requirement(must_visit=["人民公园"]))


def test_review_refinement_and_persistence_representation_preserve_identity():
    original = Requirement(must_visit=["上海迪士尼"], resolved_must_visit=[{
        "source_text": "上海迪士尼", "status": "resolved", "poi_id": 1046,
        "canonical_name": "上海迪士尼乐园", "matched_by": "alias",
        "matched_value": "上海迪士尼", "candidates": [],
    }])
    proposed = deepcopy(original); proposed.must_visit = [] ; proposed.scope = "DAY"
    refined = preserve_user_intent(original, proposed)
    assert refined.resolved_must_visit == original.resolved_must_visit
    assert "resolved_must_visit" in refined.to_dict(include_resolution=True)
    assert "resolved_must_visit" not in refined.to_dict()


def test_scoped_replan_does_not_duplicate_whole_trip_must_visit(monkeypatch):
    planner = RoutePlanner(None, Config())
    requirement = Requirement(days=4, must_visit=["上海迪士尼"], resolved_must_visit=[{
        "source_text": "上海迪士尼", "status": "resolved", "poi_id": 1046,
        "canonical_name": "上海迪士尼乐园", "matched_by": "alias",
        "matched_value": "上海迪士尼", "candidates": [],
    }])
    observed = {}

    def capture(_pois, local, _hotel):
        observed["must_visit"] = local.must_visit
        observed["resolved_must_visit"] = local.resolved_must_visit
        return [DayPlan(1, local.start_date, "测试", [])]

    monkeypatch.setattr(planner, "plan", capture)
    planner.plan_day([], requirement, object(), 2)

    assert observed == {"must_visit": [], "resolved_must_visit": []}
