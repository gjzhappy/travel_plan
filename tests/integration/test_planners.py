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
 names=[n.name for n in days[0].nodes];assert "must" in names and len(names)==4
 assert days[0].route_score!=0
def test_meals_insert_preference_budget_and_detour():
 hotel=SimpleNamespace(name="hotel",lat=31,lon=121);day=DayPlan(1,"2026-08-19","",[Node("attraction","A","09:00","10:00")])
 restaurants=[Restaurant(1,"expensive","西餐","中心",31,121,999,H),Restaurant(2,"火锅店","火锅","中心",31,121,60,H)]
 req=Requirement(start_date="2026-08-19",food_preferences=["火锅"],budget=5000)
 MealPlanner(MockMapClient(),Config()).insert(day,restaurants,req,hotel)
 assert {n.type for n in day.nodes}>={"lunch","dinner"};assert all(n.name=="火锅店" for n in day.nodes if n.type in {"lunch","dinner"})
 assert next(n for n in day.nodes if n.type=="dinner").metadata["duplicate_reason"]=="only feasible restaurant"


def test_meals_prefer_distinct_restaurants_when_multiple_are_feasible():
 hotel=SimpleNamespace(name="hotel",lat=31,lon=121);day=DayPlan(1,"2026-08-19","",[Node("attraction","A","09:00","10:00")])
 restaurants=[Restaurant(1,"first","本帮菜","中心",31,121,50,H),Restaurant(2,"second","本帮菜","中心",31,121,55,H)]
 req=Requirement(start_date="2026-08-19",food_preferences=["本帮菜"],budget=5000)
 MealPlanner(MockMapClient(),Config()).insert(day,restaurants,req,hotel)
 meals=[n for n in day.nodes if n.type in {"lunch","dinner"}]
 assert meals[0].metadata["restaurant_id"]!=meals[1].metadata["restaurant_id"]


def test_route_reserves_lunch_then_continues_with_afternoon_activity():
 hotel=SimpleNamespace(name="hotel",lat=31,lon=121)
 pois=[p(i,f"P{i}","中心",100-i) for i in range(1,5)]
 req=Requirement(days=1,start_date="2026-08-19",pace="relaxed",include_meals=True)
 day=RoutePlanner(MockMapClient(),Config()).plan(pois,req,hotel)[0]
 assert any(n.start_time>="12:30" for n in day.nodes)


def test_route_order_changes_when_transport_cost_changes():
 class DirectedTransport:
  def __init__(self, durations): self.durations=durations
  def route(self, origin, destination, preference=None):
   from travel_plan.retrieval.transport_provider import TransportResult
   duration=self.durations.get((origin.name,destination.name),5)
   return TransportResult("metro",duration,1,3,0,"rule_estimate")
 hotel=SimpleNamespace(name="hotel",lat=31,lon=121)
 pois=[p(11,"A","中心",50),p(12,"B","中心",50)]
 req=Requirement(days=1,start_date="2026-08-19",pace="relaxed",include_meals=False)
 first=RoutePlanner(DirectedTransport({("hotel","A"):5,("A","B"):5,("hotel","B"):60}),Config()).plan(pois,req,hotel)
 second=RoutePlanner(DirectedTransport({("hotel","A"):60,("hotel","B"):5,("B","A"):5}),Config()).plan(pois,req,hotel)
 assert [n.name for n in first[0].nodes]==["A","B"]
 assert [n.name for n in second[0].nodes]==["B","A"]
 assert first[0].route_score != 0 and second[0].route_score != 0


class MatrixTransport:
 def __init__(self,durations):self.durations=durations
 def route(self,origin,destination,preference=None):
  from travel_plan.retrieval.transport_provider import TransportResult
  duration=self.durations.get((origin.name,destination.name),self.durations.get((destination.name,origin.name),5))
  return TransportResult("metro",duration,1,3,0,"test_matrix")


def test_lunch_prefers_lower_detour_over_small_quality_gain():
 hotel=SimpleNamespace(name="hotel",lat=31,lon=121)
 day=DayPlan(1,"2026-08-19","",[
  Node("attraction","A","09:00","11:00",metadata={"lat":31,"lon":121}),
  Node("attraction","B","13:00","14:00",metadata={"lat":31.1,"lon":121.1}),
 ])
 near=Restaurant(1,"Near","本帮菜","one",31.01,121.01,80,H)
 far=Restaurant(2,"Far","本帮菜","two",31.5,121.5,60,H)
 transport=MatrixTransport({("A","Near"):8,("Near","B"):10,("A","Far"):35,("Far","B"):40,("A","B"):10})
 req=Requirement(start_date="2026-08-19",food_preferences=["本帮菜"],budget=5000)
 MealPlanner(transport,Config()).insert(day,[near,far],req,hotel,only_meal="lunch")
 lunch=next(n for n in day.nodes if n.type=="lunch")
 assert lunch.name=="Near" and lunch.metadata["detour_min"]==8


def test_must_eat_overrides_meal_detour():
 hotel=SimpleNamespace(name="hotel",lat=31,lon=121)
 day=DayPlan(1,"2026-08-19","",[
  Node("attraction","A","09:00","11:00",metadata={"lat":31,"lon":121}),
  Node("attraction","B","13:00","14:00",metadata={"lat":31.1,"lon":121.1}),
 ])
 near=Restaurant(1,"Near","本帮菜","one",31.01,121.01,80,H)
 far=Restaurant(2,"Far","本帮菜","two",31.5,121.5,60,H)
 transport=MatrixTransport({("A","Near"):8,("Near","B"):10,("A","Far"):35,("Far","B"):40,("A","B"):10})
 req=Requirement(start_date="2026-08-19",must_eat=["Far"],budget=5000)
 MealPlanner(transport,Config()).insert(day,[near,far],req,hotel,only_meal="lunch")
 assert next(n for n in day.nodes if n.type=="lunch").name=="Far"


def test_route_penalizes_zig_zag_but_keeps_high_value_poi():
 hotel=SimpleNamespace(name="hotel",lat=31,lon=121)
 pois=[p(21,"A","one",50),p(22,"B","two",51),p(23,"C","one",50)]
 durations={("hotel","A"):5,("hotel","B"):40,("hotel","C"):5,
            ("A","B"):40,("B","C"):40,("A","C"):10}
 req=Requirement(days=1,start_date="2026-08-19",include_meals=False)
 day=RoutePlanner(MatrixTransport(durations),Config()).plan(pois,req,hotel)[0]
 assert [n.name for n in day.nodes] != ["A","B","C"]
 assert {n.name for n in day.nodes}=={"A","B","C"}


def test_dinner_scores_complete_path_to_hotel():
 hotel=SimpleNamespace(name="hotel",lat=31,lon=121)
 day=DayPlan(1,"2026-08-19","",[Node("attraction","Last","15:00","17:00",metadata={"lat":31,"lon":121})])
 a=Restaurant(1,"A","本帮菜","one",31.1,121.1,50,H);b=Restaurant(2,"B","本帮菜","two",31.2,121.2,50,H)
 transport=MatrixTransport({("Last","A"):5,("A","hotel"):45,("Last","B"):10,("B","hotel"):10,("Last","hotel"):15})
 MealPlanner(transport,Config()).insert(day,[a,b],Requirement(start_date="2026-08-19",budget=5000),hotel,only_meal="dinner")
 dinner=next(n for n in day.nodes if n.type=="dinner")
 assert dinner.name=="B" and dinner.metadata["next_node"]=="hotel"
 hotel_return=next(n for n in day.nodes if n.type=="hotel_return")
 assert hotel_return.duration_min==10 and hotel_return.metadata["previous_node"]=="B"
