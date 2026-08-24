from dataclasses import dataclass
from datetime import datetime, timedelta
from travel_plan.models.trip import HotelSegment, Node

MIN_HOTEL_CHANGE_GAIN=60

@dataclass
class HotelDecision:
    action:str; net_gain_min:float; reason:str; change_day:int|None=None

class HotelOptimizer:
    def __init__(self,map_client,config): self.map=map_client;self.config=config
    def optimize(self,days,hotels,req,savings_override=None):
        base=hotels[0]
        def segment(h,start,end):
            return HotelSegment(h.hotel_id,h.name,start,end,h.nightly_price,
                h.supports_luggage_storage,h.check_in_time,h.check_out_time,h.lat,h.lon)
        if req.lodging_strategy=="fixed": return [segment(base,1,req.days)],HotelDecision("KEEP",0,"fixed strategy")
        eligible=[h for h in hotels[1:] if (not req.has_luggage or h.supports_luggage_storage)
                  and h.lat is not None and h.lon is not None]
        if req.max_hotel_changes==0 or not eligible:return [segment(base,1,req.days)],HotelDecision("KEEP",0,"hotel changes disabled or no storage-capable alternative")
        alt=eligible[0]; change_day=max(2,(req.days+1)//2)
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
        if gain<=threshold:return [segment(base,1,req.days)],HotelDecision("KEEP",gain,f"net gain {gain} <= threshold {threshold}")
        segments=[segment(base,1,change_day-1),segment(alt,change_day,req.days)]
        d=days[change_day-1]
        def route_meta(hotel):
            result={"route_constraint":True}
            if hasattr(hotel,"lat"):result.update({"lat":hotel.lat,"lon":hotel.lon})
            return result
        base_meta=route_meta(base);alt_meta=route_meta(alt)
        base_meta.update({"hotel_id":base.hotel_id})
        alt_meta.update({"hotel_id":alt.hotel_id})
        first_activity=min((datetime.strptime(n.start_time,"%H:%M") for n in d.nodes),default=datetime.strptime("09:00","%H:%M"))
        checkout_end=first_activity-timedelta(minutes=migration+30)
        checkout_start=checkout_end-timedelta(minutes=15)
        d.nodes.insert(0,Node("hotel_checkout",base.name,checkout_start.strftime("%H:%M"),checkout_end.strftime("%H:%M"),metadata=base_meta))
        # duration_min is the single canonical incoming Hotel A -> Hotel B leg.
        arrival=checkout_end+timedelta(minutes=migration)
        handled=arrival+timedelta(minutes=30)
        d.nodes.insert(1,Node("luggage_drop",alt.name,arrival.strftime("%H:%M"),handled.strftime("%H:%M"),transport_mode=req.transport,duration_min=migration,metadata={**alt_meta,"luggage_action":"transfer","source_hotel_id":base.hotel_id,"source_hotel":base.name,"target_hotel_id":alt.hotel_id,"target_hotel":alt.name,"handling_duration_min":30,"previous_node":base.name,"transport_source":"hotel_transfer","supports_luggage_storage":alt.supports_luggage_storage}))
        d.nodes.append(Node("hotel_checkin",alt.name,"20:30","21:00",metadata=alt_meta))
        return segments,HotelDecision("CHANGE",gain,f"net gain {gain} > threshold {threshold}",change_day)
