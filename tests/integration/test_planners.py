from types import SimpleNamespace
from travel_plan.config import Config
from travel_plan.models.poi import POI,Restaurant
from travel_plan.models.requirement import Requirement
from travel_plan.models.trip import DayPlan,Node
from travel_plan.planning.meal_planner import MealPlanner
from travel_plan.planning.route_planner import RoutePlanner
from travel_plan.retrieval.map_client import MockMapClient

H={"weekly_hours":{d:["08:00","21:00"] for d in ("mon","tue","wed","thu","fri","sat","sun")},"special_dates":{},"latest_entry_time":"18:00"}
def p(i,name,district,priority,duration=60,cat="科技"):
 x=POI(i,name,"上海",district,31+i*.001,121+i*.001,cat,10,duration,False,H);x.priority=priority;return x
def test_route_optimizes_score_region_time_and_must_visit():
 hotel=SimpleNamespace(name="hotel",lat=31,lon=121)
 pois=[p(1,"input-first","远郊",1),p(2,"must","中心",100),p(3,"near-low","中心",50),p(4,"other-category","中心",70,90,"自然")]
 req=Requirement(days=1,start_date="2026-08-19",pace="relaxed",must_visit=["must"],include_meals=False)
 days=RoutePlanner(MockMapClient({("hotel","input-first"):5,("hotel","must"):30}),Config()).plan(pois,req,hotel)
 names=[n.name for n in days[0].nodes];assert names[0]!="input-first" and "must" in names and len(names)==3
 assert days[0].route_score!=0
def test_meals_insert_preference_budget_and_detour():
 hotel=SimpleNamespace(name="hotel",lat=31,lon=121);day=DayPlan(1,"2026-08-19","",[Node("attraction","A","09:00","10:00")])
 restaurants=[Restaurant(1,"expensive","西餐","中心",31,121,999,H),Restaurant(2,"火锅店","火锅","中心",31,121,60,H)]
 req=Requirement(start_date="2026-08-19",food_preferences=["火锅"],budget=5000)
 MealPlanner(MockMapClient(),Config()).insert(day,restaurants,req,hotel)
 assert {n.type for n in day.nodes}>={"lunch","dinner"};assert all(n.name=="火锅店" for n in day.nodes if n.type in {"lunch","dinner"})

