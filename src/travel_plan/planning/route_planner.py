from datetime import date, datetime, timedelta
from itertools import combinations, permutations
from travel_plan.config import Config
from travel_plan.errors import NoFeasibleRouteError
from travel_plan.models.trip import DayPlan, Node
from travel_plan.planning.scoring import route_score
from travel_plan.retrieval.map_client import Location
from travel_plan.validation.opening_hours import hours_for_day

def _dt(day:date,clock:str): return datetime.combine(day,datetime.strptime(clock,"%H:%M").time())
def _loc(x): return Location(x.name,x.lat,x.lon)

class RoutePlanner:
    def __init__(self,transport_provider,config:Config): self.transport=transport_provider; self.config=config
    def plan(self,pois,req,hotel):
        # This is only a computational/safety ceiling.  Feasibility below (time,
        # travel, opening hours and meal reservations), rather than a pace-specific
        # POI quota, decides when a day is full.
        cap=self.config.max_pois_per_day
        remaining=list(pois); days=[]
        for index in range(req.days):
            day_date=date.fromisoformat(req.start_date)+timedelta(days=index)
            feasible=[p for p in remaining if hours_for_day(p.opening_hours,day_date)]
            # Region-aware selection, while never starving high priority must-visits.
            anchor=max(feasible,key=lambda p:p.priority,default=None)
            if not anchor: days.append(DayPlan(index+1,day_date.isoformat(),"自由活动",[])); continue
            regional=sorted(feasible,key=lambda p:(p.district!=anchor.district,-p.priority))[:self.config.route_candidate_limit]
            best=None; selected=[]
            required={p.name for p in regional if p.name in req.must_visit}
            for count in range(min(cap,len(regional)),0,-1):
                for subset in combinations(regional,count):
                    if required and not required.issubset({p.name for p in subset}): continue
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
        scheduled={n.name for d in days for n in d.nodes}; missing=set(req.must_visit)-scheduled
        if missing: raise NoFeasibleRouteError(f"must_visit cannot be scheduled: {', '.join(missing)}")
        return days
    def plan_day(self,pois,req,hotel,day_number):
        """Plan exactly one requested day; it never evaluates another day."""
        from copy import copy
        local=copy(req);local.days=1;local.start_date=(date.fromisoformat(req.start_date)+timedelta(days=day_number-1)).isoformat()
        local.must_visit=[name for name in req.must_visit if any(p.name==name for p in pois)] if day_number==1 else []
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
                nodes.append(Node("attraction",p.name,start.strftime("%H:%M"),end.strftime("%H:%M"),p.poi_id,leg.mode,leg.distance_km,leg.duration_min,p.ticket_price,{"category":p.category,"priority":p.priority,"must_visit":p.name in req.must_visit,"opening_hours":p.opening_hours,"reservation_required":p.reservation_required,"latest_entry_time":latest,"lat":p.lat,"lon":p.lon}))
                now=end+timedelta(minutes=buffer_min);current=p
            if valid:
                score=route_score(total_priority,transport+transport_penalty,waiting,max(0,(transport+sum(p.duration_min for p in order)-600)*tightness),repeated)
                if best is None or score>best[1]: best=(nodes,score)
        return best
