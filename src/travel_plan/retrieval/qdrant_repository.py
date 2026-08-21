import hashlib
import math
from typing import Iterable

def _tokens(text: str) -> set[str]:
    lowered=text.lower(); words=set(lowered.split())
    words.update(lowered[i:i+2] for i in range(max(0,len(lowered)-1)))
    return {w for w in words if w.strip()}

class OfflineSemanticRepository:
    """Deterministic token similarity used only by explicit offline/mock mode."""
    def __init__(self, documents: Iterable[dict]): self.documents=list(documents)
    def search(self, query: str, city: str, top_k: int=20) -> list[dict]:
        q=_tokens(query)
        results=[]
        for d in self.documents:
            if d.get("city") != city: continue
            tokens=_tokens(d.get("semantic_description","")+" "+d.get("text",""))
            overlap=len(q & tokens); score=overlap/math.sqrt(max(1,len(q)*len(tokens)))
            results.append({"poi_id":d["poi_id"],"semantic_score":round(score,4),"source":"offline_semantic","text":d.get("text","")})
        return sorted(results,key=lambda x:(-x["semantic_score"],x["poi_id"]))[:top_k]

class QdrantSemanticRepository:
    def __init__(self,client,collection,embed): self.client=client;self.collection=collection;self.embed=embed
    def search(self,query,city,top_k=20):
        hits=self.client.query_points(collection_name=self.collection,query=self.embed(query),query_filter={"must":[{"key":"city","match":{"value":city}}]},limit=top_k,with_payload=True).points
        return [{"poi_id":h.payload["poi_id"],"semantic_score":h.score,"source":"qdrant","text":h.payload.get("text","")} for h in hits]

# Backward-compatible offline name; runtime construction uses the honest class name.
QdrantRepository=OfflineSemanticRepository

COLLECTION_NAME = "shanghai_travel_poi"
MOCK_VECTOR_SIZE = 64


def deterministic_mock_embedding(text: str, size: int = MOCK_VECTOR_SIZE) -> list[float]:
    """Return a stable, normalized feature-hash embedding without network or model I/O."""
    vector = [0.0] * size
    for token in sorted(_tokens(text)):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % size
        vector[index] += 1.0 if digest[4] & 1 else -1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 8) for value in vector]


def qdrant_points(pois: Iterable[dict]) -> list[dict]:
    """Build deterministic Qdrant-shaped points from canonical POI source rows."""
    points = []
    for poi in pois:
        payload = {key: poi[key] for key in ("poi_id", "name", "category", "tags", "description")}
        payload["city"] = "上海"
        text = " ".join([poi["name"], poi["category"], *poi["tags"], poi["description"]])
        points.append({"id": poi["poi_id"], "vector": deterministic_mock_embedding(text), "payload": payload})
    return points
