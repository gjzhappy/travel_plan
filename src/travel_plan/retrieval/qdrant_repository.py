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
