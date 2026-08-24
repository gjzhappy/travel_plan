from dataclasses import dataclass
from datetime import date, datetime
from travel_plan.validation.opening_hours import can_visit
from travel_plan.planning.transport_quality import daily_transport_metrics, policy_for, transport_legs

@dataclass
class ValidationIssue:
    code:str; message:str; day:int|None=None; node:str|None=None; details:dict|None=None

class HardValidator:
    def __init__(self,config):self.config=config
    def validate(self,plan,req):
        issues=[]
        assignments={day:segment for segment in plan.hotels for day in range(segment.start_day,segment.end_day+1)}
        for day in plan.days:
            previous_end=None
            types=[n.type for n in day.nodes]
            ordered=sorted(day.nodes,key=lambda n:n.start_time)
            for index,n in enumerate(ordered):
                start=datetime.strptime(n.start_time,"%H:%M").time();end=datetime.strptime(n.end_time,"%H:%M").time()
                if end<=start:issues.append(ValidationIssue("invalid_duration",f"{n.name} ends before it starts",day.day,n.name))
                if previous_end and start<previous_end:issues.append(ValidationIssue("overlap",f"{n.name} overlaps previous node",day.day,n.name))
                previous_end=max(previous_end,end) if previous_end else end
                if n.type=="attraction":
                    hours=n.metadata.get("opening_hours",{})
                    if not can_visit(hours,date.fromisoformat(day.date),start,int((datetime.combine(date.today(),end)-datetime.combine(date.today(),start)).seconds/60)):
                        issues.append(ValidationIssue("poi_closed_or_late",f"{n.name} is closed, too late, or duration does not fit",day.day,n.name))
                if n.type in {"lunch","dinner"} and not can_visit(n.metadata.get("opening_hours",{}),date.fromisoformat(day.date),start,60): issues.append(ValidationIssue("restaurant_closed",f"{n.name} is closed",day.day,n.name))
                if n.metadata.get("detour_min",0)>45 and not n.metadata.get("explicit_preference"):issues.append(ValidationIssue("meal_detour",f"{n.name} detour too large",day.day,n.name))
                hotel=next((h for h in plan.hotels if h.hotel_id==n.metadata.get("hotel_id")),None)
                if n.type in {"hotel_checkout","hotel_checkin","luggage_drop"} and hotel is None:
                    issues.append(ValidationIssue("hotel_assignment_discontinuity",f"{n.name} has no canonical hotel_id assignment",day.day,n.name))
                if n.type=="luggage_drop":
                    target=hotel
                    if not target or not target.supports_luggage_storage:
                        issues.append(ValidationIssue("hotel_luggage_storage_unsupported",f"{n.name} does not have structured luggage-storage support",day.day,n.name))
                    if not target or target.lat is None or target.lon is None or n.metadata.get("lat") is None or n.metadata.get("lon") is None:
                        issues.append(ValidationIssue("hotel_transfer_missing_transport",f"{n.name} luggage transfer has no usable hotel coordinates",day.day,n.name))
                    if not n.transport_mode or n.duration_min<=0:
                        issues.append(ValidationIssue("hotel_transfer_missing_transport",f"{n.name} luggage transfer has no canonical incoming transport leg",day.day,n.name))
                if n.type=="hotel_checkin" and hotel and n.start_time < hotel.check_in_time:
                    issues.append(ValidationIssue("hotel_checkin_too_early",f"{n.start_time} is before {hotel.check_in_time}",day.day,n.name))
                if n.type=="hotel_checkout" and hotel and n.end_time > hotel.check_out_time:
                    issues.append(ValidationIssue("hotel_checkout_too_late",f"{n.end_time} is after {hotel.check_out_time}",day.day,n.name))
                if index:
                    prior=ordered[index-1]
                    prior_end=datetime.combine(date.fromisoformat(day.date),datetime.strptime(prior.end_time,"%H:%M").time())
                    current_start=datetime.combine(date.fromisoformat(day.date),start)
                    gap=int((current_start-prior_end).total_seconds()/60)
                    # Incoming travel is already represented on the destination
                    # node; only the remainder is idle time.
                    idle=max(0,gap-int(n.duration_min or 0))
                    justified_types={"hotel_checkout","luggage_drop","hotel_checkin","hotel_return"}
                    justified=(prior.type in justified_types or n.type in justified_types or
                               prior.metadata.get("idle_gap_reason") or n.metadata.get("idle_gap_reason") or
                               prior.metadata.get("reservation_wait") or n.metadata.get("reservation_wait") or
                               prior.metadata.get("user_requested_rest") or n.metadata.get("user_requested_rest"))
                    # The minimum is derived from the normal one-hour activity plus
                    # the configured moderate route buffer and a typical 20m leg.
                    minimum_fit=60+10+20
                    if idle>=minimum_fit and not justified:
                        issues.append(ValidationIssue("unreasonable_idle_gap",f"unexplained {idle} minute gap after {prior.name}",day.day,prior.name))
            if req.include_meals:
                for meal in ("lunch","dinner"):
                    if meal not in types:issues.append(ValidationIssue("missing_meal",f"missing {meal}",day.day))
                lunch=next((n for n in day.nodes if n.type=="lunch"),None);dinner=next((n for n in day.nodes if n.type=="dinner"),None)
                if lunch and dinner and lunch.metadata.get("restaurant_id")==dinner.metadata.get("restaurant_id") and not dinner.metadata.get("duplicate_reason"):
                    issues.append(ValidationIssue("duplicate_restaurant","lunch and dinner use the same restaurant without a fallback reason",day.day,dinner.name))
            if "hotel_checkout" in types:
                positions=[types.index(t) if t in types else -1 for t in ("hotel_checkout","luggage_drop","hotel_checkin")]
                if not (positions[0]<positions[1]<positions[2]):issues.append(ValidationIssue("luggage_chain", "checkout/drop/checkin luggage chain is incomplete",day.day))
                else:
                    checkout=day.nodes[positions[0]];drop=day.nodes[positions[1]];checkin=day.nodes[positions[2]]
                    if not (checkout.end_time<=drop.start_time and drop.end_time<=checkin.start_time):
                        issues.append(ValidationIssue("luggage_chain","checkout/drop/checkin timestamps are inconsistent",day.day))
            assigned=assignments.get(day.day)
            if not assigned:
                issues.append(ValidationIssue("hotel_overnight_closure_missing","day has no canonical overnight hotel assignment",day.day))
            else:
                returns=[n for n in day.nodes if n.type in {"hotel_return","hotel_checkin"}]
                if returns and returns[-1].name!=assigned.name:
                    issues.append(ValidationIssue("hotel_assignment_discontinuity",f"overnight node is not assigned hotel {assigned.name}",day.day))
                first=ordered[0] if ordered else None
                expected_start=assignments.get(day.day-1) if day.day>1 else assigned
                if first and expected_start:
                    recorded_origin=first.metadata.get("previous_node")
                    switching=first.type=="hotel_checkout" and first.name==expected_start.name
                    if recorded_origin and recorded_origin!=expected_start.name and not switching:
                        issues.append(ValidationIssue("hotel_assignment_discontinuity",f"day starts from {recorded_origin}, expected {expected_start.name}",day.day))
            metrics=daily_transport_metrics(day,self.config,req.pace)
            if metrics.quality_status=="excessive":
                policy=policy_for(self.config,req.pace)
                legs=transport_legs(day)
                ordinary=[]
                for index,leg in enumerate(legs):
                    previous=legs[index-1] if index else None
                    exceptional=(leg.type=="luggage_drop" or
                                 leg.metadata.get("accepted_long_distance") or
                                 leg.metadata.get("must_visit_related") or
                                 leg.metadata.get("must_visit") or
                                 bool(previous and previous.metadata.get("must_visit")))
                    if not exceptional:ordinary.append(leg.duration_min)
                # A hard requirement can explain the excess only when the route
                # left after removing its related legs is within preferred bounds.
                exempted=(sum(ordinary)<=policy.preferred_total_min and
                          max(ordinary,default=0)<=policy.preferred_single_leg_min)
                if not exempted:
                    threshold={"total_transport_min":policy.hard_total_min,"single_leg_min":policy.hard_single_leg_min}
                    reason="daily total exceeds hard limit" if metrics.total_transport_min>policy.hard_total_min else "single transfer exceeds hard limit"
                    details={"day":day.day,"total_transport_min":metrics.total_transport_min,"largest_transfer_min":metrics.largest_transfer_min,"threshold":threshold,"reason":reason}
                    issues.append(ValidationIssue("excessive_daily_transport",f"day {day.day} has {metrics.total_transport_min} transport minutes; largest transfer {metrics.largest_transfer_min}",day.day,details=details))
        if req.lodging_strategy=="fixed" and len(plan.hotels)>1:issues.append(ValidationIssue("fixed_hotel_violated","fixed lodging has multiple hotels"))
        if len(plan.hotels)-1>req.max_hotel_changes:issues.append(ValidationIssue("hotel_changes_exceeded","too many hotel changes"))
        if plan.budget.total>req.budget:issues.append(ValidationIssue("budget_exceeded",f"estimated {plan.budget.total} > budget {req.budget}"))
        return issues
