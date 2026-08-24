from datetime import date, datetime, timedelta
from itertools import combinations, permutations
from travel_plan.config import Config
from travel_plan.errors import MustVisitResolutionError, NoFeasibleRouteError
from travel_plan.models.trip import DayPlan, Node
from travel_plan.planning.scoring import route_score
from travel_plan.retrieval.map_client import Location
from travel_plan.validation.opening_hours import hours_for_day
from travel_plan.retrieval.poi_resolver import CanonicalPOIResolver

def _dt(day:date,clock:str): return datetime.combine(day,datetime.strptime(clock,"%H:%M").time())
def _loc(x): return Location(x.name,x.lat,x.lon)
def _must_visit_ids(req): return {item["poi_id"] for item in req.resolved_must_visit}

class RoutePlanner:
    def __init__(self,transport_provider,config:Config): self.transport=transport_provider; self.config=config
    def plan(self,pois,req,hotel):
        # RoutePlanner may be used directly by library callers. Use the same exact
        # resolver boundary there; never perform fuzzy matching in route search.
        if req.must_visit and not req.resolved_must_visit:
            resolutions = [CanonicalPOIResolver(list(pois)).resolve(text) for text in req.must_visit]
            failed = next((item for item in resolutions if item.status != "resolved"), None)
            if failed:
                raise MustVisitResolutionError(f"must_visit identity is {failed.status}: {failed.source_text}")
            req.resolved_must_visit = [item.to_dict() for item in resolutions]
        # This is only a computational/safety ceiling.  Feasibility below (time,
        # travel, opening hours and meal reservations), rather than a pace-specific
        # POI quota, decides when a day is full.
        cap=self.config.max_pois_per_day
        remaining=list(pois); days=[]
        for index in range(req.days):
            day_date=date.fromisoformat(req.start_date)+timedelta(days=index)
            feasible=[p for p in remaining if hours_for_day(p.opening_hours,day_date)]
            # Candidate retrieval is relevance-led. Spatial decisions below use
            # provider durations, never administrative district labels.
            if not feasible: days.append(DayPlan(index+1,day_date.isoformat(),"自由活动",[])); continue
            anchor=max(feasible,key=lambda p:p.priority)
            required_ids=_must_visit_ids(req)
            required_candidates=[p for p in feasible if p.poi_id in required_ids]
            optional=sorted(
                (p for p in feasible if p.poi_id not in required_ids),
                key=lambda p:-(p.priority-self.transport.route(_loc(anchor),_loc(p),req.transport).duration_min*.7),
            )
            regional=(required_candidates+optional)[:max(self.config.route_candidate_limit,len(required_candidates))]
            best=None; selected=[]
            required={p.poi_id for p in regional if p.poi_id in required_ids}
            for count in range(min(cap,len(regional)),0,-1):
                for subset in combinations(regional,count):
                    if required and not required.issubset({p.poi_id for p in subset}): continue
                    candidate=self._best_order(subset,day_date,hotel,req)
                    if candidate and (best is None or candidate[1]>best[1]): best=candidate;selected=list(subset)
                if best: break
            if not best: raise NoFeasibleRouteError(f"day {index+1} has no feasible route")
            nodes,score=best; used={n.poi_id for n in nodes if n.poi_id}; remaining=[p for p in remaining if p.poi_id not in used]
            if index==req.days-1:
                # Every remaining candidate has now been evaluated for this final
                # day and rejected by the same travel/opening/duration constraints.
                for node in nodes:node.metadata["idle_gap_reason"]="no feasible remaining candidate"
            days.append(DayPlan(index+1,day_date.isoformat()," / ".join(dict.fromkeys(p.category for p in selected)),nodes,score))
        scheduled={n.poi_id for d in days for n in d.nodes}; missing=_must_visit_ids(req)-scheduled
        if missing:
            names=[item["canonical_name"] for item in req.resolved_must_visit if item["poi_id"] in missing]
            raise NoFeasibleRouteError(f"must_visit cannot be scheduled: {', '.join(names)}")
        return days
    def plan_day(self,pois,req,hotel,day_number):
        """Plan exactly one requested day; it never evaluates another day."""
        from copy import copy
        local=copy(req);local.days=1;local.start_date=(date.fromisoformat(req.start_date)+timedelta(days=day_number-1)).isoformat()
        local.resolved_must_visit=[item for item in req.resolved_must_visit if any(p.poi_id==item["poi_id"] for p in pois)] if day_number==1 else []
        result=self.plan(pois,local,hotel)[0];result.day=day_number
        return result
    def _best_order(self,pois,day,hotel,req):
        mode=req.transport
        pace={"relaxed":(15,"20:00",1.4),"moderate":(10,"21:00",1.0),"intensive":(5,"22:00",.7)}[req.pace]
        buffer_min,latest_end,tightness=pace
        best=None
        mobility_sensitive = bool(req.party.child) or req.walking=="low" or bool(
            {"亲子", "家庭", "儿童", "老人", "老年"}.intersection(req.interests)
        )
        for order in permutations(pois):
            now=_dt(day,self.config.daily_start_time); current=hotel; nodes=[]; total_priority=transport=transport_penalty=waiting=repeated=0; previous_cat=None; valid=True
            locations=[hotel]
            for p in order:
                leg=self.transport.route(_loc(current),_loc(p),mode); arrival=now+timedelta(minutes=leg.duration_min); window=hours_for_day(p.opening_hours,day)
                if not window: valid=False;break
                start=max(arrival,datetime.combine(day,window[0])); latest=p.opening_hours.get("latest_entry_time")
                # Meals are real reservations in the route search, not nodes
                # mechanically appended after every attraction has been placed.
                if req.include_meals:
                    for meal_start,meal_end in (self.config.lunch_window,self.config.dinner_window):
                        reserved_start=_dt(day,meal_start);reserved_end=reserved_start+timedelta(minutes=60)
                        if start < reserved_end and start+timedelta(minutes=p.duration_min) > reserved_start:
                            start=reserved_end
                    # Night activities are optional.  This pass ends attraction
                    # packing at dinner so a restaurant/hotel return can remain
                    # executable; a future explicit night reservation can override.
                    if start>=_dt(day,self.config.dinner_window[0]):
                        valid=False;break
                if latest and start.time()>datetime.strptime(latest,"%H:%M").time():valid=False;break
                end=start+timedelta(minutes=p.duration_min)
                if end.time()>window[1] or end>_dt(day,min(self.config.daily_latest_end_time,latest_end)):valid=False;break
                wait=max(0,int((start-arrival).total_seconds()/60)); waiting+=wait; transport+=leg.duration_min
                if mobility_sensitive:
                    transport_penalty += leg.walking_minutes + leg.transfer_count * 10
                elif req.walking=="high" or req.budget <= 1000:
                    transport_penalty += leg.duration_min * (0.15 if leg.mode=="taxi" else 0)
                repeated+=int(previous_cat==p.category); previous_cat=p.category; total_priority+=p.priority
                nodes.append(Node("attraction",p.canonical_name,start.strftime("%H:%M"),end.strftime("%H:%M"),p.poi_id,leg.mode,leg.distance_km,leg.duration_min,p.ticket_price,{"category":p.category,"priority":p.priority,"must_visit":p.poi_id in _must_visit_ids(req),"opening_hours":p.opening_hours,"reservation_required":p.reservation_required,"latest_entry_time":latest,"lat":p.lat,"lon":p.lon}))
                locations.append(p);now=end+timedelta(minutes=buffer_min);current=p
            if valid:
                discontinuity=0
                for a,b,c in zip(locations,locations[1:],locations[2:]):
                    via=(self.transport.route(_loc(a),_loc(b),mode).duration_min+
                         self.transport.route(_loc(b),_loc(c),mode).duration_min)
                    direct=self.transport.route(_loc(a),_loc(c),mode).duration_min
                    discontinuity+=max(0,via-direct)
                score=route_score(total_priority,transport+transport_penalty,waiting,max(0,(transport+sum(p.duration_min for p in order)-600)*tightness),repeated,discontinuity)
                if best is None or score>best[1]: best=(nodes,score)
        return best
