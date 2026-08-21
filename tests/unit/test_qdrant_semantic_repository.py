from qdrant_client import QdrantClient, models

from travel_plan.retrieval.embedding_provider import EmbeddingProvider
from travel_plan.retrieval.qdrant_repository import COLLECTION_NAME, QdrantSemanticRepository


class QueryProvider(EmbeddingProvider):
    @property
    def dimension(self):
        return 2

    def embed_batch(self, texts):
        return [[1.0, 0.0] for _ in texts]


def test_qdrant_guide_candidates_expand_to_sqlite_poi_ids():
    client = QdrantClient(":memory:")
    client.create_collection(COLLECTION_NAME, vectors_config=models.VectorParams(size=2, distance=models.Distance.COSINE))
    client.upsert(
        COLLECTION_NAME,
        points=[models.PointStruct(id=1, vector=[1.0, 0.0], payload={
            "type": "guide", "city": "上海", "guide_id": "guide_017",
            "text": "外滩、东方明珠和北外滩夜景路线", "poi_ids": [1001, 1002, 1006],
        })],
        wait=True,
    )
    assert client.collection_exists(COLLECTION_NAME)
    results = QdrantSemanticRepository(client, QueryProvider()).search("上海晚上看夜景路线", "上海", 10)
    assert {item["poi_id"] for item in results} == {1001, 1002, 1006}
    assert all(item["source"] == "qdrant" for item in results)
