import math
from typing import Iterable

def _tokens(text: str) -> set[str]:
    lowered=text.lower(); words=set(lowered.split())
    words.update(lowered[i:i+2] for i in range(max(0,len(lowered)-1)))
    return {w for w in words if w.strip()}

class QdrantRepository:
    """Qdrant facade with deterministic in-memory semantic fallback for offline demos."""
    def __init__(self, documents: Iterable[dict]): self.documents=list(documents)
    def search(self, query: str, city: str, top_k: int=20) -> list[dict]:
        q=_tokens(query)
        results=[]
        for d in self.documents:
            if d.get("city") != city: continue
            tokens=_tokens(d.get("semantic_description","")+" "+d.get("text",""))
            overlap=len(q & tokens); score=overlap/math.sqrt(max(1,len(q)*len(tokens)))
            results.append({"poi_id":d["poi_id"],"semantic_score":round(score,4),"source":"qdrant_mock","text":d.get("text","")})
        return sorted(results,key=lambda x:(-x["semantic_score"],x["poi_id"]))[:top_k]

