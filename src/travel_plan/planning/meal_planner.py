from datetime import date, datetime, timedelta
from travel_plan.models.trip import Node
from travel_plan.retrieval.map_client import Location
from travel_plan.validation.opening_hours import can_visit

def _loc(x,fallback=None):
    if isinstance(x,Node):
        if "lat" not in x.metadata and fallback is not None:return _loc(fallback)
        return Location(x.name,float(x.metadata["lat"]),float(x.metadata["lon"]))
    return Location(x.name,x.lat,x.lon)

class MealPlanner:
    def __init__(self,map_client,config): self.map=map_client;self.config=config
    def insert(self,day,restaurants,req,hotel,only_meal=None):
        if not req.include_meals:return day
        kinds=((only_meal,getattr(self.config,f"{only_meal}_window")),) if only_meal else (("lunch",self.config.lunch_window),("dinner",self.config.dinner_window))
        used_restaurants={n.metadata.get("restaurant_id") for n in day.nodes if n.type in {"lunch","dinner"}}
        for meal,window in kinds:
            day.nodes[:]=[n for n in day.nodes if n.type!=meal]
            attractions=[n for n in day.nodes if n.type=="attraction"]
            if meal=="lunch":
                # Anchor lunch at the first permissible meal slot. Attractions
                # reserved after that slot belong to the afternoon and are shifted
                # only by the actual restaurant legs below.
                before=[n for n in attractions if n.end_time<=window[0]]; previous=before[-1] if before else hotel
                after=[n for n in attractions if n.start_time>=window[0] and n is not previous]; next_node=after[0] if after else hotel
            else:
                previous=attractions[-1] if attractions else hotel;next_node=hotel
            candidates=[];day_date=date.fromisoformat(day.date); at=datetime.strptime(window[0],"%H:%M").time()
            for r in restaurants:
                if not can_visit(r.opening_hours,day_date,at,60):continue
                cost=r.price_per_person*(req.party.adult+req.party.child)
                if cost>max(1,req.budget)*.12:continue
                a=self.map.route(_loc(previous,hotel),_loc(r),req.transport);b=self.map.route(_loc(r),_loc(next_node,hotel),req.transport);direct=self.map.route(_loc(previous,hotel),_loc(next_node,hotel),req.transport)
                detour=max(0,a.duration_min+b.duration_min-direct.duration_min)
                if detour>45:continue
                pref=40 if r.cuisine in req.food_preferences else 0
                duplicate = r.restaurant_id in used_restaurants
                candidates.append((duplicate,pref-detour-r.price_per_person*.05,r,detour,a,b,cost))
            if not candidates:continue
            # Exclude an already-used restaurant whenever another feasible choice
            # exists.  A duplicate remains a deterministic fallback for a sparse DB.
            distinct=[item for item in candidates if not item[0]]
            duplicate,_,r,detour,leg,next_leg,cost=max(distinct or candidates,key=lambda x:x[1])
            arrival=(datetime.combine(day_date,datetime.strptime(previous.end_time if isinstance(previous,Node) else window[0],"%H:%M").time())+timedelta(minutes=leg.duration_min))
            start=max(arrival,datetime.combine(day_date,at));end=start+timedelta(minutes=60)
            node=Node(meal,r.name,start.strftime("%H:%M"),end.strftime("%H:%M"),None,req.transport,leg.distance_km,leg.duration_min,cost,{"restaurant_id":r.restaurant_id,"cuisine":r.cuisine,"price_per_person":r.price_per_person,"detour_min":detour,"opening_hours":r.opening_hours,"lat":r.lat,"lon":r.lon,"next_travel_min":next_leg.duration_min,"previous_node":previous.name,"next_node":next_node.name,"duplicate_reason":"only feasible restaurant" if duplicate else None})
            pos=day.nodes.index(previous)+1 if isinstance(previous,Node) and previous in day.nodes else len(day.nodes);day.nodes.insert(pos,node)
            if isinstance(next_node,Node):
                earliest=end+timedelta(minutes=next_leg.duration_min);current=datetime.combine(day_date,datetime.strptime(next_node.start_time,"%H:%M").time())
                shift=max(0,int((earliest-current).total_seconds()/60))
                if shift:
                    start_index=day.nodes.index(next_node)
                    for later in day.nodes[start_index:]:
                        a=datetime.combine(day_date,datetime.strptime(later.start_time,"%H:%M").time())+timedelta(minutes=shift);b=datetime.combine(day_date,datetime.strptime(later.end_time,"%H:%M").time())+timedelta(minutes=shift)
                        later.start_time=a.strftime("%H:%M");later.end_time=b.strftime("%H:%M")
            used_restaurants.add(r.restaurant_id)
        day.nodes.sort(key=lambda n:n.start_time)
        return day
