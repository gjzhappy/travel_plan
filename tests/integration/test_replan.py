from copy import deepcopy
from travel_plan.conversation.replanner import Replanner
from travel_plan.models.trip import Budget,DayPlan,Node,TripPlan

def plan(prefix):return TripPlan("x",[DayPlan(i,"2026-08-19","",[Node("attraction",f"{prefix}{i}","09:00","10:00"),Node("dinner",f"meal{prefix}{i}","18:00","19:00")]) for i in range(1,4)],[],Budget())
def test_all_scopes_and_lock():
 old,new=plan("a"),plan("b");r=Replanner()
 assert r.apply("GLOBAL",old,new).days[0].nodes[0].name=="b1"
 day=r.apply("DAY",old,new,2);assert day.days[0].nodes[0].name=="a1" and day.days[1].nodes[0].name=="b2"
 node=r.apply("NODE",old,new,2);assert node.days[1].nodes[0].name=="b2"
 meal=r.apply("MEAL",old,new,2,"dinner");assert meal.days[1].nodes[0].name=="a2" and meal.days[1].nodes[1].name=="mealb2"
 locked=r.apply("DAY",old,new,1,locked_items=["DAY:1"]);assert locked.days[0].nodes[0].name=="a1"

