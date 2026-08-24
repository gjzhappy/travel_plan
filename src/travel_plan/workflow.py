import logging, uuid
from time import monotonic
from copy import deepcopy
from dataclasses import asdict
from travel_plan.agents.requirement_agent import OpenCodeRequirementAgent
from travel_plan.agents.review_agent import OpenCodeReviewAgent
from travel_plan.config import DEFAULT_CONFIG
from travel_plan.conversation.state_manager import StateManager,TripState
from travel_plan.conversation.replanner import Replanner
from travel_plan.errors import AmbiguousTargetNodeError,LockedPlanConflict,ValidationError
from travel_plan.models.requirement import Requirement
from travel_plan.models.trip import Budget,TripPlan
from travel_plan.observability.event_trace import EventTrace
from travel_plan.planning.hotel_optimizer import HotelOptimizer
from travel_plan.planning.meal_planner import MealPlanner
from travel_plan.planning.route_planner import RoutePlanner
from travel_plan.renderer.markdown_renderer import MarkdownRenderer
from travel_plan.validation.repair import CodeRepair
from travel_plan.validation.validator import HardValidator
from travel_plan.planning.transport_quality import daily_transport_metrics

log=logging.getLogger("travel_plan")
class TravelWorkflow:
    def __init__(self,retrieval,facts,map_client,state_dir="data/state",config=DEFAULT_CONFIG,agent_client=None):
        self.retrieval=retrieval;self.facts=facts;self.map=map_client;self.state=StateManager(state_dir);self.config=config
        self.requirements=OpenCodeRequirementAgent(agent_client)
        self.reviewer=OpenCodeReviewAgent(agent_client)
        self.events=EventTrace(state_dir)
        self.route=RoutePlanner(map_client,config);self.meals=MealPlanner(map_client,config);self.hotels=HotelOptimizer(map_client,config);self.validator=HardValidator(config)
    def execute(self,text,trip_id=None):
        trip_id=trip_id or f"trip_{uuid.uuid4().hex[:8]}";prior=self.state.load(trip_id);existing=Requirement.from_dict(prior.requirements) if prior else None
        version=1 if prior is None else prior.version+1;parent_version=prior.version if prior else None
        self._event(trip_id,version,parent_version,"WORKFLOW_STARTED","workflow",{"has_prior_plan":prior is not None})
        started=monotonic();self._event(trip_id,version,parent_version,"STAGE_STARTED","requirement-agent",{"stage":"REQUIREMENT"})
        parsed=self.requirements.parse(text,existing,prior.current_plan if prior else None)
        req,intent=parsed
        self._event(trip_id,version,parent_version,"AGENT_COMPLETED","requirement-agent",{"scope":intent.get("scope","GLOBAL"),"duration_ms":self._elapsed(started)})
        locked=list(prior.locked_items) if prior else []
        lock_day=intent.get("lock_day")
        if lock_day:
            item=f"DAY:{lock_day}"
            if item not in locked:locked.append(item)
        started=monotonic();self._event(trip_id,version,parent_version,"STAGE_STARTED","retrieval",{"stage":"RETRIEVAL"})
        hotels=self.facts.hotels(req.city);restaurants=self.facts.restaurants(req.city);shortlist=self.retrieval.shortlist(req)
        self._event(trip_id,version,parent_version,"STAGE_COMPLETED","retrieval",{"stage":"RETRIEVAL","duration_ms":self._elapsed(started),"candidate_count":len(shortlist)})
        started=monotonic();self._event(trip_id,version,parent_version,"STAGE_STARTED","planner",{"stage":"PLANNER"})
        if prior and lock_day: plan=_plan_from_dict(prior.current_plan)
        elif not prior or intent["scope"]=="GLOBAL": plan=self._global(trip_id,shortlist,req,hotels,restaurants,version,parent_version)
        else: plan=self._local(_plan_from_dict(prior.current_plan),shortlist,req,hotels,restaurants,intent,prior.locked_items,version,parent_version)
        self._event(trip_id,version,parent_version,"PLAN_GENERATED","planner",{"scope":intent["scope"],"duration_ms":self._elapsed(started)})
        plan,req=self._validate_review_replan(plan,shortlist,req,hotels,restaurants,locked,version,parent_version)
        version=self.state.next_version(trip_id);state=TripState(trip_id,version,req.to_dict(include_resolution=True),locked,req.rejected_pois,req.rejected_categories,plan.to_dict());self.state.save(state)
        self._event(trip_id,version,parent_version,"PLAN_VERSION_SAVED","state-manager",{"change":"LOCK_DAY" if lock_day else "PLAN","lock_day":lock_day})
        return plan.to_dict(),state,MarkdownRenderer().render(plan)
    def _global(self,trip_id,shortlist,req,hotels,restaurants,version,parent_version):
        started=monotonic();self._event(trip_id,version,parent_version,"STAGE_STARTED","route-planner",{"stage":"ROUTE_PLANNING"})
        days=self.route.plan(shortlist,req,hotels[0])
        self._event(trip_id,version,parent_version,"STAGE_COMPLETED","route-planner",{"stage":"ROUTE_PLANNING","duration_ms":self._elapsed(started)})
        started=monotonic();self._event(trip_id,version,parent_version,"STAGE_STARTED","hotel-optimizer",{"stage":"HOTEL_PLANNING"})
        segments,decision=self.hotels.optimize(days,hotels,req)
        self._event(trip_id,version,parent_version,"STAGE_COMPLETED","hotel-optimizer",{"stage":"HOTEL_PLANNING","duration_ms":self._elapsed(started)})
        started=monotonic();self._event(trip_id,version,parent_version,"STAGE_STARTED","meal-planner",{"stage":"MEAL_PLANNING"})
        hotel_by_id={hotel.hotel_id:hotel for hotel in hotels}
        for day in days:
            assigned=next(segment for segment in segments if segment.start_day<=day.day<=segment.end_day)
            hotel=hotel_by_id[assigned.hotel_id]
            first=next((node for node in sorted(day.nodes,key=lambda node:node.start_time) if node.type=="attraction"),None)
            if first and first.metadata.get("previous_node")!=hotel.name:
                from travel_plan.retrieval.map_client import Location
                leg=self.map.route(Location(hotel.name,hotel.lat,hotel.lon),Location(first.name,first.metadata["lat"],first.metadata["lon"]),req.transport)
                first.transport_mode=leg.mode;first.distance_km=leg.distance_km;first.duration_min=leg.duration_min
                first.metadata.update({"previous_node":hotel.name,"transport_source":leg.source})
            self.meals.insert(day,restaurants,req,hotel)
        self._event(trip_id,version,parent_version,"STAGE_COMPLETED","meal-planner",{"stage":"MEAL_PLANNING","duration_ms":self._elapsed(started)})
        plan=TripPlan(trip_id,days,segments,Budget(),asdict(decision));self.recompute_derived(plan,req);return plan
    def _local(self,plan,shortlist,req,hotels,restaurants,intent,locked,version,parent_version):
        day_no=intent.get("day") or req.target_day
        if not day_no: raise AmbiguousTargetNodeError("local modification has no target day")
        if f"DAY:{day_no}" in locked: raise LockedPlanConflict(f"day {day_no} is locked")
        day=next(d for d in plan.days if d.day==day_no);scope=intent["scope"]
        if scope=="DAY":
            candidates,required_ids=self._scoped_candidates(plan,shortlist,req,scope,day_no)
            replacement=self.route.plan_day(candidates,req,hotels[0],day_no,required_ids);self.meals.insert(replacement,restaurants,req,hotels[0]);plan.days[plan.days.index(day)]=replacement
        elif scope=="MEAL": self.meals.insert(day,restaurants,req,hotels[0],intent.get("meal") or req.target_meal)
        elif scope=="NODE":
            matches=[n for n in day.nodes if n.type=="attraction" and ((req.target_node_id and str(n.poi_id)==req.target_node_id) or (req.target_poi_name and n.name==req.target_poi_name))]
            if len(matches)!=1: raise AmbiguousTargetNodeError("target node must resolve to exactly one attraction")
            target=matches[0];protected,_=self._scoped_candidates(plan,shortlist,req,scope,day_no,target.poi_id)
            used={n.poi_id for d in plan.days for n in d.nodes};candidates=[p for p in protected if p.poi_id not in used and p.name not in req.rejected_pois]
            if not candidates: raise AmbiguousTargetNodeError("no eligible replacement node")
            p=max(candidates,key=lambda x:x.priority);target.name=p.name;target.poi_id=p.poi_id;target.cost=p.ticket_price;target.metadata.update({"category":p.category,"priority":p.priority,"lat":p.lat,"lon":p.lon,"must_visit":p.name in req.must_visit})
            self.meals.insert(day,restaurants,req,hotels[0])
        self.recompute_derived(plan,req);return plan
    def _validate_review_replan(self,plan,shortlist,req,hotels,restaurants,locked,version,parent_version):
        validation_started=monotonic();self._event(plan.trip_id,version,parent_version,"STAGE_STARTED","validator",{"stage":"VALIDATOR"})
        issues=self.validator.validate(plan,req)
        self._validator_event(plan.trip_id,version,parent_version,"INITIAL",issues)
        if issues:
            plan=CodeRepair().repair(plan,issues,req,restaurants);self.recompute_derived(plan,req);issues=self.validator.validate(plan,req)
            self._validator_event(plan.trip_id,version,parent_version,"AFTER_REPAIR",issues)
        self._event(plan.trip_id,version,parent_version,"STAGE_COMPLETED","validator",{"stage":"VALIDATOR","duration_ms":self._elapsed(validation_started),"passed":not bool(issues)})
        review=None
        for retry in range(self.config.review_max_retries+1):
            review_started=monotonic();self._event(plan.trip_id,version,parent_version,"STAGE_STARTED","review-agent",{"stage":"REVIEW","review_number":plan.review_count+1})
            review=self.reviewer.review(req,plan,plan.evidence);plan.review_count+=1
            self._event(plan.trip_id,version,parent_version,"REVIEW_COMPLETED","review-agent",{"review_number":plan.review_count,"passed":review.passed,"issues":[asdict(issue) for issue in review.issues],"duration_ms":self._elapsed(review_started)})
            if review.passed:break
            if retry==self.config.review_max_retries:break
            # The review message returns to the intent layer before any code acts.
            # Agents communicate JSON, while Python retains all planning authority.
            refinement_started=monotonic()
            self._event(plan.trip_id,version,parent_version,"STAGE_STARTED","requirement-agent",{"stage":"REQUIREMENT_REFINEMENT","iteration":plan.review_count})
            req=self.requirements.refine(req,review,plan)
            self._event(plan.trip_id,version,parent_version,"STAGE_COMPLETED","requirement-agent",{"stage":"REQUIREMENT_REFINEMENT","iteration":plan.review_count,"scope":req.scope,"duration_ms":self._elapsed(refinement_started)})
            shortlist=self.retrieval.shortlist(req)
            scope=req.scope;affected=req.target_day;did_replan=False
            replan_started=monotonic()
            self._event(plan.trip_id,version,parent_version,"STAGE_STARTED","replanner",{"stage":"SCOPED_REPLAN","iteration":plan.review_count,"scope":scope,"target_day":affected})
            if scope=="GLOBAL":
                review_count=plan.review_count
                candidate=self._global(plan.trip_id,shortlist,req,hotels,restaurants,version,parent_version)
                plan=Replanner().apply("GLOBAL",plan,candidate,locked_items=locked)
                plan.review_count=review_count
                did_replan=True
            elif affected and f"DAY:{affected}" not in locked:
                target_id=req.target_node_id
                if scope=="NODE" and not target_id and req.target_poi_name:
                    affected_day=next(day for day in plan.days if day.day==affected)
                    target=next((node for node in affected_day.nodes if node.type=="attraction" and node.name==req.target_poi_name),None)
                    target_id=target.poi_id if target else None
                candidates,required_ids=self._scoped_candidates(plan,shortlist,req,scope,affected,target_id)
                replacement=self.route.plan_day(candidates,req,hotels[0],affected,required_ids);self.meals.insert(replacement,restaurants,req,hotels[0])
                candidate=deepcopy(plan);old=next(d for d in candidate.days if d.day==affected);candidate.days[candidate.days.index(old)]=replacement
                plan=Replanner().apply(scope,plan,candidate,affected,req.target_meal,locked)
                did_replan=True
            if did_replan:
                self._event(plan.trip_id,version,parent_version,"STAGE_COMPLETED","replanner",{"stage":"SCOPED_REPLAN","iteration":plan.review_count,"trigger_review_number":plan.review_count,"scope":scope,"target_day":affected,"duration_ms":self._elapsed(replan_started)})
            else:
                self._event(plan.trip_id,version,parent_version,"STAGE_FAILED","replanner",{"stage":"SCOPED_REPLAN","iteration":plan.review_count,"scope":scope,"target_day":affected,"duration_ms":self._elapsed(replan_started)})
            revalidation_started=monotonic();self._event(plan.trip_id,version,parent_version,"STAGE_STARTED","validator",{"stage":"HARD_VALIDATION","iteration":plan.review_count})
            self.recompute_derived(plan,req);issues=self.validator.validate(plan,req)
            self._validator_event(plan.trip_id,version,parent_version,"AFTER_REPLAN",issues)
            if issues:plan=CodeRepair().repair(plan,issues,req,restaurants);self.recompute_derived(plan,req);issues=self.validator.validate(plan,req)
            self._event(plan.trip_id,version,parent_version,"STAGE_COMPLETED","validator",{"stage":"HARD_VALIDATION","iteration":plan.review_count,"passed":not bool(issues),"duration_ms":self._elapsed(revalidation_started)})
        # Acceptance is fail-closed: review exhaustion may leave experience
        # findings for display, but no plan with a hard validation issue may be
        # returned, rendered, or persisted as the current state.
        final_started=monotonic();self._event(plan.trip_id,version,parent_version,"STAGE_STARTED","validator",{"stage":"FINAL_VALIDATION"})
        issues=self.validator.validate(plan,req)
        self._validator_event(plan.trip_id,version,parent_version,"FINAL_GATE",issues)
        self._event(plan.trip_id,version,parent_version,"STAGE_FAILED" if issues else "STAGE_COMPLETED","validator",{"stage":"FINAL_VALIDATION","passed":not bool(issues),"duration_ms":self._elapsed(final_started)})
        if issues:
            details="; ".join(f"{issue.code}: {issue.message}" for issue in issues)
            raise ValidationError(f"plan rejected by final validation gate: {details}")
        plan.remaining_issues=[asdict(x) for x in (review.issues if review and not review.passed else [])]
        return plan,req
    @staticmethod
    def _scoped_candidates(plan,shortlist,req,scope,day_number,target_poi_id=None):
        """Exclude stable attraction identities owned by unaffected trip scope."""
        target_id=int(target_poi_id) if target_poi_id and str(target_poi_id).isdigit() else None
        protected_poi_ids=set()
        target_day_ids=set()
        for day in plan.days:
            for node in day.nodes:
                if node.type!="attraction" or node.poi_id is None:
                    continue
                in_scope=day.day==day_number and (scope=="DAY" or (scope=="NODE" and node.poi_id==target_id))
                if in_scope:
                    target_day_ids.add(node.poi_id)
                else:
                    protected_poi_ids.add(node.poi_id)
        required={item["poi_id"] for item in req.resolved_must_visit}
        required_on_target=required & target_day_ids
        candidates=[poi for poi in shortlist if poi.poi_id not in protected_poi_ids or poi.poi_id in required_on_target]
        return candidates,required_on_target
    def _event(self,trip_id,version,parent_version,event_type,actor,details=None):
        self.events.record(trip_id,version,parent_version,event_type,actor,details)
    def _validator_event(self,trip_id,version,parent_version,stage,issues):
        self._event(trip_id,version,parent_version,"VALIDATOR_BLOCKED" if issues else "VALIDATOR_PASSED","validator",{"stage":stage,"issues":[asdict(issue) for issue in issues]})
    @staticmethod
    def _elapsed(started):
        return max(0.0,(monotonic()-started)*1000.0)
    def recompute_derived(self,plan,req):
        people=req.party.adult+req.party.child
        plan.budget=Budget(tickets=sum(n.cost*people for d in plan.days for n in d.nodes if n.type=="attraction"),meals=sum(n.cost for d in plan.days for n in d.nodes if n.type in {"lunch","dinner"}),hotels=sum(s.nightly_price*(s.end_day-s.start_day+1) for s in plan.hotels),transport=sum(n.duration_min*.3 for d in plan.days for n in d.nodes if n.transport_mode))
        for day in plan.days:
            day.transport_metrics=asdict(daily_transport_metrics(day,self.config,req.pace))
        plan.evidence=[{"day":d.day,"poi_ids":[n.poi_id for n in d.nodes if n.poi_id],"route_score":d.route_score,"transport_metrics":d.transport_metrics} for d in plan.days]

def _plan_from_dict(raw):
    from travel_plan.models.trip import Budget,DayPlan,HotelSegment,Node,TripPlan
    days=[DayPlan(d["day"],d["date"],d["theme"],[Node(**n) for n in d["nodes"]],d.get("route_score",0),d.get("transport_metrics",{})) for d in raw["days"]];b=dict(raw["budget"]);b.pop("total",None)
    return TripPlan(raw["trip_id"],days,[HotelSegment(**h) for h in raw["hotels"]],Budget(**b),raw.get("hotel_decision",{}),raw.get("evidence",[]),raw.get("remaining_issues",[]),raw.get("review_count",0))
