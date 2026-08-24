from dataclasses import dataclass
from datetime import date, datetime
from travel_plan.validation.opening_hours import can_visit

@dataclass
class ValidationIssue:
    code:str; message:str; day:int|None=None; node:str|None=None

class HardValidator:
    def __init__(self,config):self.config=config
    def validate(self,plan,req):
        issues=[]
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
        if req.lodging_strategy=="fixed" and len(plan.hotels)>1:issues.append(ValidationIssue("fixed_hotel_violated","fixed lodging has multiple hotels"))
        if len(plan.hotels)-1>req.max_hotel_changes:issues.append(ValidationIssue("hotel_changes_exceeded","too many hotel changes"))
        if plan.budget.total>req.budget:issues.append(ValidationIssue("budget_exceeded",f"estimated {plan.budget.total} > budget {req.budget}"))
        return issues
