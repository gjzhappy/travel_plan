import math
from collections.abc import Iterable

from travel_plan.retrieval.embedding_provider import EmbeddingProvider

COLLECTION_NAME = "shanghai_travel_poi"


def _tokens(text: str) -> set[str]:
    lowered = text.lower()
    words = set(lowered.split())
    words.update(lowered[i : i + 2] for i in range(max(0, len(lowered) - 1)))
    return {word for word in words if word.strip()}


class OfflineSemanticRepository:
    """Deterministic lexical fallback used only by lightweight unit tests."""

    def __init__(self, documents: Iterable[dict]):
        self.documents = list(documents)

    def search(self, query: str, city: str, top_k: int = 20) -> list[dict]:
        query_tokens = _tokens(query)
        results = []
        for document in self.documents:
            if document.get("city") != city:
                continue
            tokens = _tokens(document.get("semantic_description", "") + " " + document.get("text", ""))
            overlap = len(query_tokens & tokens)
            score = overlap / math.sqrt(max(1, len(query_tokens) * len(tokens)))
            results.append({"poi_id": document["poi_id"], "semantic_score": round(score, 4), "source": "offline_semantic", "text": document.get("text", "")})
        return sorted(results, key=lambda item: (-item["semantic_score"], item["poi_id"]))[:top_k]


class QdrantSemanticRepository:
    """Semantic knowledge search; routing decisions remain outside this class."""

    def __init__(self, client, provider: EmbeddingProvider, collection: str = COLLECTION_NAME):
        self.client = client
        self.provider = provider
        self.collection = collection

    def search(self, query: str, city: str, top_k: int = 20) -> list[dict]:
        from qdrant_client import models

        hits = self.client.query_points(
            collection_name=self.collection,
            query=self.provider.embed(query),
            query_filter=models.Filter(must=[models.FieldCondition(key="city", match=models.MatchValue(value=city))]),
            limit=top_k,
            with_payload=True,
        ).points
        candidates: dict[int, dict] = {}
        for hit in hits:
            payload = hit.payload
            poi_ids = [payload["poi_id"]] if payload["type"] == "poi" else payload.get("poi_ids", [])
            for poi_id in poi_ids:
                existing = candidates.get(poi_id)
                item = {"poi_id": poi_id, "semantic_score": float(hit.score), "source": "qdrant", "text": payload.get("text", payload.get("description", ""))}
                if existing is None or item["semantic_score"] > existing["semantic_score"]:
                    candidates[poi_id] = item
        return sorted(candidates.values(), key=lambda item: (-item["semantic_score"], item["poi_id"]))[:top_k]


# Compatibility for the explicitly lightweight mock workflow.
QdrantRepository = OfflineSemanticRepository


def qdrant_points(pois: Iterable[dict], guides: Iterable[dict], provider: EmbeddingProvider) -> list[dict]:
    """Embed POIs and guides as one typed Shanghai knowledge collection."""
    pois = list(pois)
    guides = list(guides)
    names_to_ids = {poi["name"]: poi["poi_id"] for poi in pois}

    def resolve_poi(reference: str) -> int | None:
        exact = names_to_ids.get(reference)
        if exact is not None:
            return exact
        matches = [poi_id for name, poi_id in names_to_ids.items() if reference in name or name in reference]
        return min(matches) if matches else None
    records: list[tuple[str, dict]] = []
    for poi in pois:
        payload = {key: poi[key] for key in ("poi_id", "name", "category", "tags", "description")}
        payload.update({"canonical_name": poi.get("canonical_name", poi["name"]), "aliases": poi.get("aliases", [])})
        payload.update({"type": "poi", "city": "上海"})
        text = " ".join([poi["name"], poi["category"], *poi["tags"], poi["description"]])
        records.append((text, payload))
    for guide in guides:
        payload = dict(guide)
        resolved = [resolve_poi(name) for name in guide["poi_refs"]]
        payload.update({"type": "guide", "city": "上海", "poi_ids": [poi_id for poi_id in resolved if poi_id is not None]})
        records.append((" ".join([guide["title"], guide["travel_style"], guide["text"], *guide["poi_refs"]]), payload))
    vectors = provider.embed_batch([text for text, _ in records])
    return [{"id": index + 1, "vector": vector, "payload": payload} for index, (vector, (_, payload)) in enumerate(zip(vectors, records))]
