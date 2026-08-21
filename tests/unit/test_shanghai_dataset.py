import json
from pathlib import Path

from travel_plan.retrieval.qdrant_repository import COLLECTION_NAME, MOCK_VECTOR_SIZE, qdrant_points


def test_shanghai_source_has_required_coverage_and_qdrant_payloads():
    pois = json.loads(Path("data/source/shanghai_pois.json").read_text(encoding="utf-8"))
    assert 50 <= len(pois) <= 100
    assert {p["category"] for p in pois} == {"城市地标", "历史文化", "博物馆", "亲子景点", "自然公园", "夜景商业", "小众特色"}
    points = qdrant_points(pois)
    assert COLLECTION_NAME == "shanghai_travel_poi"
    assert len(points) == len(pois)
    assert set(points[0]["payload"]) >= {"poi_id", "name", "category", "tags", "description"}
    assert len(points[0]["vector"]) == MOCK_VECTOR_SIZE
    assert points == qdrant_points(pois)
