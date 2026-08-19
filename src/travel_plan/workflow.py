import logging, uuid
from dataclasses import asdict
from travel_plan.agents.requirement_agent import RequirementAgent
from travel_plan.agents.review_agent import ReviewAgent
from travel_plan.config import DEFAULT_CONFIG
from travel_plan.conversation.replanner import Replanner
from travel_plan.conversation.state_manager import StateManager,TripState
from travel_plan.models.requirement import Requirement
from travel_plan.models.trip import Budget,TripPlan
from travel_plan.planning.hotel_optimizer import HotelOptimizer
from travel_plan.planning.meal_planner import MealPlanner
from travel_plan.planning.route_planner import RoutePlanner
from travel_plan.renderer.markdown_renderer import MarkdownRenderer
from travel_plan.validation.repair import CodeRepair
from travel_plan.validation.validator import HardValidator

log=logging.getLogger("travel_plan")
class TravelWorkflow:
    def __init__(self,retrieval,facts,map_client,state_dir="data/state",config=DEFAULT_CONFIG):
        self.retrieval=retrieval;self.facts=facts;self.map=map_client;self.state=StateManager(state_dir);self.config=config
        self.requirements=RequirementAgent();self.route=RoutePlanner(map_client,config);self.meals=MealPlanner(map_client,config);self.hotels=HotelOptimizer(map_client,config);self.validator=HardValidator(config);self.reviewer=ReviewAgent();self.replanner=Replanner()
    def execute(self,text,trip_id=None):
        trip_id=trip_id or f"trip_{uuid.uuid4().hex[:8]}";prior=self.state.load(trip_id);existing=Requirement.from_dict(prior.requirements) if prior else None
        log.info("[TRAVEL][REQUIREMENT][START]");req,intent=self.requirements.parse(text,existing)
        if prior and intent["lock_day"]:
            locked=list(prior.locked_items);item=f"DAY:{intent['lock_day']}"
            if item not in locked:locked.append(item)
            state=TripState(trip_id,prior.version+1,req.to_dict(),locked,req.rejected_pois,req.rejected_categories,prior.current_plan);self.state.save(state)
            return prior.current_plan,state,MarkdownRenderer().render(_plan_from_dict(prior.current_plan))
        shortlist=self.retrieval.shortlist(req);log.info("[TRAVEL][RETRIEVAL][DONE]")
        hotels=self.facts.hotels(req.city);restaurants=self.facts.restaurants(req.city)
        days=self.route.plan(shortlist,req,hotels[0]);log.info("[TRAVEL][ROUTE][DONE]")
        for day in days:self.meals.insert(day,restaurants,req,hotels[0])
        segments,decision=self.hotels.optimize(days,hotels,req)
        plan=TripPlan(trip_id,days,segments,Budget(),asdict(decision));self._budget(plan,req)
        issues=self.validator.validate(plan,req)
        if issues:plan=CodeRepair().repair(plan,issues,req,restaurants);self._budget(plan,req);issues=self.validator.validate(plan,req)
        review=None
        for attempt in range(self.config.review_max_retries+1):
            review=self.reviewer.review(req,plan,plan.evidence);plan.review_count+=1
            if review.passed:break
            for issue in review.issues:
                if issue.day:
                    day=next(d for d in plan.days if d.day==issue.day);attrs=[n for n in day.nodes if n.type=="attraction" and n.name not in req.must_visit]
                    if attrs:day.nodes.remove(min(attrs,key=lambda n:n.metadata.get("priority",0)))
            if attempt==self.config.review_max_retries:break
        plan.remaining_issues=[asdict(x) for x in (review.issues if review and not review.passed else [])]+[asdict(x) for x in issues]
        if prior:plan=self.replanner.apply(intent["scope"],_plan_from_dict(prior.current_plan),plan,intent["day"],intent["meal"],prior.locked_items)
        version=self.state.next_version(trip_id);state=TripState(trip_id,version,req.to_dict(),prior.locked_items if prior else [],req.rejected_pois,req.rejected_categories,plan.to_dict());self.state.save(state)
        return plan.to_dict(),state,MarkdownRenderer().render(plan)
    def _budget(self,plan,req):
        people=req.party.adult+req.party.child
        plan.budget.tickets=sum(n.cost*people for d in plan.days for n in d.nodes if n.type=="attraction")
        plan.budget.meals=sum(n.cost for d in plan.days for n in d.nodes if n.type in {"lunch","dinner"})
        plan.budget.hotels=sum(s.nightly_price*(s.end_day-s.start_day+1) for s in plan.hotels)
        plan.budget.transport=sum(n.duration_min*.3 for d in plan.days for n in d.nodes if n.transport_mode)

def _plan_from_dict(raw):
    from travel_plan.models.trip import Budget,DayPlan,HotelSegment,Node,TripPlan
    days=[DayPlan(d["day"],d["date"],d["theme"],[Node(**n) for n in d["nodes"]],d.get("route_score",0)) for d in raw["days"]]
    b=dict(raw["budget"]);b.pop("total",None)
    return TripPlan(raw["trip_id"],days,[HotelSegment(**h) for h in raw["hotels"]],Budget(**b),raw.get("hotel_decision",{}),raw.get("evidence",[]),raw.get("remaining_issues",[]),raw.get("review_count",0))
