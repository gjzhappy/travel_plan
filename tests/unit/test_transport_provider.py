from travel_plan.retrieval.map_client import Location
from travel_plan.retrieval.transport_provider import HierarchicalMockTransportProvider


def test_popular_route_comes_from_cache():
    provider = HierarchicalMockTransportProvider()

    result = provider.route(
        Location("外滩", 31.25, 121.48),
        Location("东方明珠", 31.35, 121.58),
    )

    assert result.source == "mock_cache"
    assert result.mode == "metro"
    assert result.duration_min == 15


def test_uncached_route_uses_stable_rule_estimate():
    provider = HierarchicalMockTransportProvider()
    origin = Location("非热门甲", 31.11, 121.21)
    destination = Location("非热门乙", 31.28, 121.61)

    results = [provider.route(origin, destination) for _ in range(10)]

    assert results[0].source == "rule_estimate"
    assert all(result == results[0] for result in results)
