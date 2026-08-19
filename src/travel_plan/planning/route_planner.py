from datetime import date, datetime, timedelta
from itertools import permutations
from travel_plan.config import Config
from travel_plan.errors import NoFeasibleRouteError
from travel_plan.models.trip import DayPlan, Node
from travel_plan.planning.scoring import route_score
from travel_plan.retrieval.map_client import Location
from travel_plan.validation.opening_hours import hours_for_day

def _dt(day:date,clock:str): return datetime.combine(day,datetime.strptime(clock,"%H:%M").time())
def _loc(x): return Location(x.name,x.lat,x.lon)

class RoutePlanner:
    def __init__(self,map_client,config:Config): self.map=map_client; self.config=config
    def plan(self,pois,req,hotel):
        limits={"relaxed":3,"moderate":4,"intensive":5}; cap=min(limits[req.pace],self.config.max_pois_per_day)
        remaining=list(pois); days=[]
        for index in range(req.days):
            day_date=date.fromisoformat(req.start_date)+timedelta(days=index)
            feasible=[p for p in remaining if hours_for_day(p.opening_hours,day_date)]
            # Region-aware selection, while never starving high priority must-visits.
            anchor=max(feasible,key=lambda p:p.priority,default=None)
            if not anchor: days.append(DayPlan(index+1,day_date.isoformat(),"自由活动",[])); continue
            regional=sorted(feasible,key=lambda p:(p.district!=anchor.district,-p.priority))[:cap+2]
            selected=regional[:cap]
            best=self._best_order(selected,day_date,hotel,req.transport)
            if not best:
                for count in range(len(selected)-1,0,-1):
                    best=self._best_order(selected[:count],day_date,hotel,req.transport)
                    if best: break
            if not best: raise NoFeasibleRouteError(f"day {index+1} has no feasible route")
            nodes,score=best; used={n.poi_id for n in nodes if n.poi_id}; remaining=[p for p in remaining if p.poi_id not in used]
            days.append(DayPlan(index+1,day_date.isoformat()," / ".join(dict.fromkeys(p.category for p in selected)),nodes,score))
        scheduled={n.name for d in days for n in d.nodes}; missing=set(req.must_visit)-scheduled
        if missing: raise NoFeasibleRouteError(f"must_visit cannot be scheduled: {', '.join(missing)}")
        return days
    def _best_order(self,pois,day,hotel,mode):
        best=None
        for order in permutations(pois):
            now=_dt(day,self.config.daily_start_time); current=hotel; nodes=[]; total_priority=transport=waiting=repeated=0; previous_cat=None; valid=True
            for p in order:
                leg=self.map.route(_loc(current),_loc(p),mode); arrival=now+timedelta(minutes=leg.duration_min); window=hours_for_day(p.opening_hours,day)
                if not window: valid=False;break
                start=max(arrival,datetime.combine(day,window[0])); latest=p.opening_hours.get("latest_entry_time")
                if latest and start.time()>datetime.strptime(latest,"%H:%M").time():valid=False;break
                end=start+timedelta(minutes=p.duration_min)
                if end.time()>window[1] or end>_dt(day,self.config.daily_latest_end_time):valid=False;break
                wait=max(0,int((start-arrival).total_seconds()/60)); waiting+=wait; transport+=leg.duration_min
                repeated+=int(previous_cat==p.category); previous_cat=p.category; total_priority+=p.priority
                nodes.append(Node("attraction",p.name,start.strftime("%H:%M"),end.strftime("%H:%M"),p.poi_id,mode,leg.distance_km,leg.duration_min,p.ticket_price,{"category":p.category,"priority":p.priority,"must_visit":p.name in [],"opening_hours":p.opening_hours,"reservation_required":p.reservation_required,"latest_entry_time":latest}))
                now=end;current=p
            if valid:
                score=route_score(total_priority,transport,waiting,max(0,transport+sum(p.duration_min for p in order)-600),repeated)
                if best is None or score>best[1]: best=(nodes,score)
        return best

