from dataclasses import dataclass
from travel_plan.models.trip import HotelSegment, Node

MIN_HOTEL_CHANGE_GAIN=60

@dataclass
class HotelDecision:
    action:str; net_gain_min:float; reason:str; change_day:int|None=None

class HotelOptimizer:
    def __init__(self,map_client,config): self.map=map_client;self.config=config
    def optimize(self,days,hotels,req,savings_override=None):
        base=hotels[0]
        if req.lodging_strategy=="fixed": return [HotelSegment(base.hotel_id,base.name,1,req.days,base.nightly_price)],HotelDecision("KEEP",0,"fixed strategy")
        if req.max_hotel_changes==0 or len(hotels)<2:return [HotelSegment(base.hotel_id,base.name,1,req.days,base.nightly_price)],HotelDecision("KEEP",0,"hotel changes disabled")
        alt=hotels[1]; change_day=max(2,(req.days+1)//2)
        if savings_override is None:
            from travel_plan.retrieval.map_client import Location
            def loc_node(n): return Location(n.name,float(n.metadata["lat"]),float(n.metadata["lon"]))
            def commute(h,nodes):
                if not nodes:return 0
                hl=Location(h.name,h.lat,h.lon)
                return self.map.route(hl,loc_node(nodes[0]),req.transport).duration_min+self.map.route(loc_node(nodes[-1]),hl,req.transport).duration_min
            saving=0
            for day in days[change_day-1:]:
                attractions=[n for n in day.nodes if n.type=="attraction"]
                saving+=commute(base,attractions)-commute(alt,attractions)
        else:saving=savings_override
        from travel_plan.retrieval.map_client import Location
        migration=30 if savings_override is not None else self.map.route(Location(base.name,base.lat,base.lon),Location(alt.name,alt.lat,alt.lon),req.transport).duration_min
        handling=35;luggage_penalty=25 if req.has_luggage else 0;extra=max(0,alt.nightly_price-base.nightly_price)*(req.days-change_day+1)/10
        gain=round(saving-migration-handling-luggage_penalty-extra,1); threshold=self.config.hotel_change_min_gain
        if gain<=threshold:return [HotelSegment(base.hotel_id,base.name,1,req.days,base.nightly_price)],HotelDecision("KEEP",gain,f"net gain {gain} <= threshold {threshold}")
        segments=[HotelSegment(base.hotel_id,base.name,1,change_day-1,base.nightly_price),HotelSegment(alt.hotel_id,alt.name,change_day,req.days,alt.nightly_price)]
        d=days[change_day-1]
        def route_meta(hotel):
            result={"route_constraint":True}
            if hasattr(hotel,"lat"):result.update({"lat":hotel.lat,"lon":hotel.lon})
            return result
        base_meta=route_meta(base);alt_meta=route_meta(alt)
        d.nodes.insert(0,Node("hotel_checkout",base.name,"08:00","08:15",metadata=base_meta))
        d.nodes.insert(1,Node("luggage_drop",alt.name,"08:15","08:45",transport_mode=req.transport,duration_min=migration,metadata={**alt_meta,"from_hotel":base.name}))
        d.nodes.append(Node("hotel_checkin",alt.name,"20:30","21:00",metadata=alt_meta))
        return segments,HotelDecision("CHANGE",gain,f"net gain {gain} > threshold {threshold}",change_day)
