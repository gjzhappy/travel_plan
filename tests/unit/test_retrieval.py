from datetime import date
from travel_plan.models.poi import POI
from travel_plan.models.requirement import Requirement
from travel_plan.retrieval.qdrant_repository import QdrantRepository
from travel_plan.retrieval.service import RetrievalService
from travel_plan.retrieval.weather_client import MockWeatherClient

H={"weekly_hours":{d:["09:00","18:00"] for d in ("mon","tue","wed","thu","fri","sat","sun")},"special_dates":{},"latest_entry_time":"17:00"}
class Facts:
 def __init__(self):self.p=[POI(1,"科技园","上海","浦东",0,0,"科技",20,60,False,H,"",True),POI(2,"博物馆A","上海","黄浦",0,0,"博物馆",30,60,False,H)]
 def get_pois(self,ids):return [p for p in self.p if p.poi_id in ids]
 def all_pois(self,city):return self.p
def test_similarity_filters_must_weather_and_fact_source():
 q=QdrantRepository([{"poi_id":1,"city":"上海","semantic_description":"科技 自然"},{"poi_id":2,"city":"上海","semantic_description":"历史"}])
 req=Requirement(start_date="2026-08-19",interests=["科技"],must_visit=["科技园"],rejected_categories=["博物馆"],retrieval_query="科技")
 service=RetrievalService(q,Facts(),MockWeatherClient({"2026-08-19":{"condition":"rain","precipitation_probability":90}}))
 result=service.shortlist(req);assert [p.name for p in result]==["科技园"]
 assert "must_visit +1000" in result[0].score_reasons and "rainy_outdoor -25" in result[0].score_reasons
 assert result[0].ticket_price==20

