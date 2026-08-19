from types import SimpleNamespace
from travel_plan.agents.review_agent import ReviewAgent
from travel_plan.config import Config
from travel_plan.models.requirement import Requirement
from travel_plan.models.trip import Budget,DayPlan,Node,TripPlan
from travel_plan.planning.hotel_optimizer import HotelOptimizer
from travel_plan.retrieval.map_client import MockMapClient

hotels=[SimpleNamespace(hotel_id=1,name="A",district="黄浦",nightly_price=300),SimpleNamespace(hotel_id=2,name="B",district="浦东",nightly_price=300)]
days=[DayPlan(i,"2026-08-19","浦东",[]) for i in range(1,5)]
def test_hotel_keep_change_fixed_zero():
 opt=HotelOptimizer(MockMapClient(),Config())
 flexible=Requirement(days=4,lodging_strategy="flexible",max_hotel_changes=1)
 assert opt.optimize(days,hotels,flexible,savings_override=120)[1].action=="KEEP"
 assert opt.optimize(days,hotels,flexible,savings_override=250)[1].action=="CHANGE"
 assert opt.optimize(days,hotels,Requirement(days=4,lodging_strategy="fixed"),500)[1].action=="KEEP"
 assert opt.optimize(days,hotels,Requirement(days=4,lodging_strategy="flexible",max_hotel_changes=0),500)[1].action=="KEEP"
def test_review_pass_tiring_repetitive_and_no_mutation():
 req=Requirement(pace="relaxed",interests=[]);nodes=[Node("attraction",str(i),"09:00","10:00",metadata={"category":"博物馆"}) for i in range(4)]
 plan=TripPlan("x",[DayPlan(1,"2026-08-19","",nodes)],[],Budget());before=plan.to_dict();review=ReviewAgent().review(req,plan)
 assert not review.passed and {i.type for i in review.issues}>={"too_tiring","content_repetitive"};assert plan.to_dict()==before
 assert ReviewAgent().review(Requirement(interests=[]),TripPlan("x",[],[],Budget())).passed

