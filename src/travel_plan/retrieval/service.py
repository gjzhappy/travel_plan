from datetime import date, timedelta
from travel_plan.models.requirement import Requirement
from travel_plan.validation.opening_hours import hours_for_day

class RetrievalService:
    def __init__(self,vectors,facts,weather,top_k=24): self.vectors=vectors; self.facts=facts; self.weather=weather; self.top_k=top_k
    def shortlist(self,req:Requirement):
        hits=self.vectors.search(req.retrieval_query or " ".join(req.interests+req.must_visit),req.city,self.top_k)
        by_id={h["poi_id"]:h for h in hits}; pois=self.facts.get_pois(list(by_id))
        # must-visits are force-added from the authoritative fact store.
        for p in self.facts.all_pois(req.city):
            if p.name in req.must_visit and p.poi_id not in by_id: pois.append(p); by_id[p.poi_id]={"semantic_score":0,"source":"forced","text":""}
        result=[]
        rainy=any(self.weather.get_forecast(req.city,date.fromisoformat(req.start_date)+timedelta(days=i)).precipitation_probability>=60 for i in range(req.days))
        for p in pois:
            if p.name in req.rejected_pois or p.category in req.rejected_categories: continue
            if not any(hours_for_day(p.opening_hours,date.fromisoformat(req.start_date)+timedelta(days=i)) for i in range(req.days)): continue
            p.similarity=by_id[p.poi_id]["semantic_score"]; p.priority=p.similarity*100
            p.score_reasons=[f"semantic_similarity +{p.similarity*100:.1f}"]
            if p.name in req.must_visit: p.priority+=1000;p.score_reasons.append("must_visit +1000")
            if rainy and p.outdoor: p.priority-=25;p.score_reasons.append("rainy_outdoor -25")
            if p.duration_min>600: p.priority-=50;p.score_reasons.append("excessive_duration -50")
            result.append(p)
        return sorted(result,key=lambda p:-p.priority)
