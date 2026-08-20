import logging, uuid
from copy import deepcopy
from dataclasses import asdict
from travel_plan.agents.requirement_agent import RequirementAgent,OpenCodeRequirementAgent
from travel_plan.agents.review_agent import ReviewAgent,OpenCodeReviewAgent
from travel_plan.config import DEFAULT_CONFIG
from travel_plan.conversation.state_manager import StateManager,TripState
from travel_plan.conversation.replanner import Replanner
from travel_plan.errors import AmbiguousTargetNodeError,LockedPlanConflict,ValidationError
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
    def __init__(self,retrieval,facts,map_client,state_dir="data/state",config=DEFAULT_CONFIG,agent_client=None):
        self.retrieval=retrieval;self.facts=facts;self.map=map_client;self.state=StateManager(state_dir);self.config=config
        self.requirements=OpenCodeRequirementAgent(agent_client) if agent_client else RequirementAgent()
        self.reviewer=OpenCodeReviewAgent(agent_client) if agent_client else ReviewAgent()
        self.route=RoutePlanner(map_client,config);self.meals=MealPlanner(map_client,config);self.hotels=HotelOptimizer(map_client,config);self.validator=HardValidator(config)
    def execute(self,text,trip_id=None):
        trip_id=trip_id or f"trip_{uuid.uuid4().hex[:8]}";prior=self.state.load(trip_id);existing=Requirement.from_dict(prior.requirements) if prior else None
        parsed=self.requirements.parse(text,existing,prior.current_plan if prior else None) if isinstance(self.requirements,OpenCodeRequirementAgent) else self.requirements.parse(text,existing)
        req,intent=parsed
        if prior and intent.get("lock_day"):
            locked=list(prior.locked_items);item=f"DAY:{intent['lock_day']}"
            if item not in locked:locked.append(item)
            state=TripState(trip_id,prior.version+1,req.to_dict(),locked,req.rejected_pois,req.rejected_categories,prior.current_plan);self.state.save(state)
            return prior.current_plan,state,MarkdownRenderer().render(_plan_from_dict(prior.current_plan))
        hotels=self.facts.hotels(req.city);restaurants=self.facts.restaurants(req.city);shortlist=self.retrieval.shortlist(req)
        if not prior or intent["scope"]=="GLOBAL": plan=self._global(trip_id,shortlist,req,hotels,restaurants)
        else: plan=self._local(_plan_from_dict(prior.current_plan),shortlist,req,hotels,restaurants,intent,prior.locked_items)
        plan,req=self._validate_review_replan(plan,shortlist,req,hotels,restaurants,prior.locked_items if prior else [])
        version=self.state.next_version(trip_id);state=TripState(trip_id,version,req.to_dict(),prior.locked_items if prior else [],req.rejected_pois,req.rejected_categories,plan.to_dict());self.state.save(state)
        return plan.to_dict(),state,MarkdownRenderer().render(plan)
    def _global(self,trip_id,shortlist,req,hotels,restaurants):
        days=self.route.plan(shortlist,req,hotels[0])
        for day in days:self.meals.insert(day,restaurants,req,hotels[0])
        segments,decision=self.hotels.optimize(days,hotels,req)
        plan=TripPlan(trip_id,days,segments,Budget(),asdict(decision));self.recompute_derived(plan,req);return plan
    def _local(self,plan,shortlist,req,hotels,restaurants,intent,locked):
        day_no=intent.get("day") or req.target_day
        if not day_no: raise AmbiguousTargetNodeError("local modification has no target day")
        if f"DAY:{day_no}" in locked: raise LockedPlanConflict(f"day {day_no} is locked")
        day=next(d for d in plan.days if d.day==day_no);scope=intent["scope"]
        if scope=="DAY":
            replacement=self.route.plan_day(shortlist,req,hotels[0],day_no);self.meals.insert(replacement,restaurants,req,hotels[0]);plan.days[plan.days.index(day)]=replacement
        elif scope=="MEAL": self.meals.insert(day,restaurants,req,hotels[0],intent.get("meal") or req.target_meal)
        elif scope=="NODE":
            matches=[n for n in day.nodes if n.type=="attraction" and ((req.target_node_id and str(n.poi_id)==req.target_node_id) or (req.target_poi_name and n.name==req.target_poi_name))]
            if len(matches)!=1: raise AmbiguousTargetNodeError("target node must resolve to exactly one attraction")
            target=matches[0];used={n.poi_id for d in plan.days for n in d.nodes};candidates=[p for p in shortlist if p.poi_id not in used and p.name not in req.rejected_pois]
            if not candidates: raise AmbiguousTargetNodeError("no eligible replacement node")
            p=max(candidates,key=lambda x:x.priority);target.name=p.name;target.poi_id=p.poi_id;target.cost=p.ticket_price;target.metadata.update({"category":p.category,"priority":p.priority,"lat":p.lat,"lon":p.lon,"must_visit":p.name in req.must_visit})
            self.meals.insert(day,restaurants,req,hotels[0])
        self.recompute_derived(plan,req);return plan
    def _validate_review_replan(self,plan,shortlist,req,hotels,restaurants,locked):
        issues=self.validator.validate(plan,req)
        if issues: plan=CodeRepair().repair(plan,issues,req,restaurants);self.recompute_derived(plan,req);issues=self.validator.validate(plan,req)
        review=None
        for retry in range(self.config.review_max_retries+1):
            review=self.reviewer.review(req,plan,plan.evidence);plan.review_count+=1
            if review.passed:break
            if retry==self.config.review_max_retries:break
            # The review message returns to the intent layer before any code acts.
            # Agents communicate JSON, while Python retains all planning authority.
            req=self.requirements.refine(req,review,plan)
            shortlist=self.retrieval.shortlist(req)
            scope=req.scope;affected=req.target_day
            if scope=="GLOBAL":
                review_count=plan.review_count
                candidate=self._global(plan.trip_id,shortlist,req,hotels,restaurants)
                plan=Replanner().apply("GLOBAL",plan,candidate,locked_items=locked)
                plan.review_count=review_count
            elif affected and f"DAY:{affected}" not in locked:
                replacement=self.route.plan_day(shortlist,req,hotels[0],affected);self.meals.insert(replacement,restaurants,req,hotels[0])
                candidate=deepcopy(plan);old=next(d for d in candidate.days if d.day==affected);candidate.days[candidate.days.index(old)]=replacement
                plan=Replanner().apply(scope,plan,candidate,affected,req.target_meal,locked)
            self.recompute_derived(plan,req);issues=self.validator.validate(plan,req)
            if issues:plan=CodeRepair().repair(plan,issues,req,restaurants);self.recompute_derived(plan,req);issues=self.validator.validate(plan,req)
        # Acceptance is fail-closed: review exhaustion may leave experience
        # findings for display, but no plan with a hard validation issue may be
        # returned, rendered, or persisted as the current state.
        issues=self.validator.validate(plan,req)
        if issues:
            details="; ".join(f"{issue.code}: {issue.message}" for issue in issues)
            raise ValidationError(f"plan rejected by final validation gate: {details}")
        plan.remaining_issues=[asdict(x) for x in (review.issues if review and not review.passed else [])]
        return plan,req
    def recompute_derived(self,plan,req):
        people=req.party.adult+req.party.child
        plan.budget=Budget(tickets=sum(n.cost*people for d in plan.days for n in d.nodes if n.type=="attraction"),meals=sum(n.cost for d in plan.days for n in d.nodes if n.type in {"lunch","dinner"}),hotels=sum(s.nightly_price*(s.end_day-s.start_day+1) for s in plan.hotels),transport=sum(n.duration_min*.3 for d in plan.days for n in d.nodes if n.transport_mode))
        plan.evidence=[{"day":d.day,"poi_ids":[n.poi_id for n in d.nodes if n.poi_id],"route_score":d.route_score} for d in plan.days]

def _plan_from_dict(raw):
    from travel_plan.models.trip import Budget,DayPlan,HotelSegment,Node,TripPlan
    days=[DayPlan(d["day"],d["date"],d["theme"],[Node(**n) for n in d["nodes"]],d.get("route_score",0)) for d in raw["days"]];b=dict(raw["budget"]);b.pop("total",None)
    return TripPlan(raw["trip_id"],days,[HotelSegment(**h) for h in raw["hotels"]],Budget(**b),raw.get("hotel_decision",{}),raw.get("evidence",[]),raw.get("remaining_issues",[]),raw.get("review_count",0))
