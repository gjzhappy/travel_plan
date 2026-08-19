from datetime import date, datetime, timedelta
from travel_plan.retrieval.map_client import Location
from travel_plan.validation.opening_hours import can_visit

def _loc(x): return Location(x.name,x.lat,x.lon)

class MealPlanner:
    def __init__(self,map_client,config): self.map=map_client;self.config=config
    def insert(self,day,restaurants,req,hotel):
        if not req.include_meals:return day
        # Rebuild chronologically; lunch is inserted after the last attraction ending before 13:30.
        for meal,window in (("lunch",self.config.lunch_window),("dinner",self.config.dinner_window)):
            if any(n.type==meal for n in day.nodes):continue
            candidates=[]; day_date=date.fromisoformat(day.date)
            anchor=next((n for n in reversed(day.nodes) if n.type=="attraction"),None)
            anchor_obj=next((r for r in restaurants if r.name==getattr(anchor,"name",None)),hotel) if anchor else hotel
            for r in restaurants:
                at=datetime.strptime(window[0],"%H:%M").time()
                if not can_visit(r.opening_hours,day_date,at,60):continue
                if r.price_per_person*(req.party.adult+req.party.child)>max(1,req.budget)*0.12:continue
                a=self.map.route(_loc(anchor_obj),_loc(r),req.transport); b=self.map.route(_loc(r),_loc(hotel),req.transport); direct=self.map.route(_loc(anchor_obj),_loc(hotel),req.transport)
                detour=max(0,a.duration_min+b.duration_min-direct.duration_min)
                if detour>45:continue
                pref=40 if r.cuisine in req.food_preferences else 0
                candidates.append((pref-detour-r.price_per_person*.05,r,detour,a))
            if not candidates:continue
            _,r,detour,leg=max(candidates,key=lambda x:x[0]); start=window[0]; end=(datetime.combine(day_date,datetime.strptime(start,"%H:%M").time())+timedelta(minutes=60)).strftime("%H:%M")
            from travel_plan.models.trip import Node
            node=Node(meal,r.name,start,end,None,req.transport,leg.distance_km,leg.duration_min,r.price_per_person*(req.party.adult+req.party.child),{"cuisine":r.cuisine,"price_per_person":r.price_per_person,"detour_min":detour,"opening_hours":r.opening_hours})
            if meal=="lunch":
                pos=next((i for i,n in enumerate(day.nodes) if n.start_time>=window[1]),len(day.nodes));day.nodes.insert(pos,node)
            else:day.nodes.append(node)
        day.nodes.sort(key=lambda n:n.start_time)
        return day

