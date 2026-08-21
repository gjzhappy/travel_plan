import json
from pathlib import Path

from travel_plan.retrieval.embedding_provider import EmbeddingProvider
from travel_plan.retrieval.qdrant_repository import COLLECTION_NAME, qdrant_points


class StableProvider(EmbeddingProvider):
    @property
    def dimension(self):
        return 3

    def embed_batch(self, texts):
        return [[float(len(text)), 1.0, 0.0] for text in texts]


def test_shanghai_source_has_required_knowledge_coverage_and_payloads():
    pois = json.loads(Path("data/source/shanghai_pois.json").read_text(encoding="utf-8"))
    guides = json.loads(Path("data/source/shanghai_guides.json").read_text(encoding="utf-8"))
    assert len(pois) >= 80
    assert 30 <= len(guides) <= 50
    points = qdrant_points(pois, guides, StableProvider())
    assert COLLECTION_NAME == "shanghai_travel_poi"
    assert len(points) == len(pois) + len(guides)
    assert sum(point["payload"]["type"] == "poi" for point in points) == len(pois)
    assert sum(point["payload"]["type"] == "guide" for point in points) == len(guides)
    assert set(points[0]["payload"]) >= {"type", "poi_id", "name", "category", "tags", "description"}
    guide = next(point for point in points if point["payload"]["type"] == "guide")
    assert set(guide["payload"]) >= {"guide_id", "title", "text", "poi_refs", "poi_ids", "travel_style"}
    assert all(len(point["vector"]) == StableProvider().dimension for point in points)
    assert points == qdrant_points(pois, guides, StableProvider())
