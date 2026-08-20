from copy import deepcopy
from travel_plan.config import Config
from travel_plan.conversation.replanner import Replanner
from travel_plan.models.requirement import Requirement
from travel_plan.models.trip import Budget,DayPlan,Node,TripPlan
from travel_plan.validation.validator import HardValidator

def plan(prefix):return TripPlan("x",[DayPlan(i,"2026-08-19","",[Node("attraction",f"{prefix}{i}","09:00","10:00"),Node("dinner",f"meal{prefix}{i}","18:00","19:00")]) for i in range(1,4)],[],Budget())
def test_all_scopes_and_lock():
 old,new=plan("a"),plan("b");r=Replanner()
 assert r.apply("GLOBAL",old,new).days[0].nodes[0].name=="b1"
 day=r.apply("DAY",old,new,2);assert day.days[0].nodes[0].name=="a1" and day.days[1].nodes[0].name=="b2"
 node=r.apply("NODE",old,new,2);assert node.days[1].nodes[0].name=="b2"
 meal=r.apply("MEAL",old,new,2,"dinner");assert meal.days[1].nodes[0].name=="a2" and meal.days[1].nodes[1].name=="mealb2"
 locked=r.apply("DAY",old,new,1,locked_items=["DAY:1"]);assert locked.days[0].nodes[0].name=="a1"


def test_day_replan_is_checked_for_hidden_overlap():
 old=plan("a")
 replacement=deepcopy(old)
 replacement.days[1].nodes=[Node("attraction","A","09:00","10:00"),Node("attraction","B","10:00","11:00"),Node("attraction","C","10:30","12:00")]

 replanned=Replanner().apply("DAY",old,replacement,2)
 issues=HardValidator(Config()).validate(replanned,Requirement(include_meals=False))

 assert any(issue.code=="overlap" and issue.day==2 and issue.node=="C" for issue in issues)
