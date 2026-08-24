from types import SimpleNamespace

from travel_plan.config import Config
from travel_plan.models.requirement import Requirement
from travel_plan.models.trip import Budget, DayPlan, HotelSegment, Node, TripPlan
from travel_plan.planning.hotel_optimizer import HotelOptimizer
from travel_plan.planning.transport_quality import daily_transport_metrics
from travel_plan.retrieval.map_client import MockMapClient
from travel_plan.validation.validator import HardValidator


def hotel(hotel_id, name, *, storage=True, lat=31.0, lon=121.0):
    return SimpleNamespace(hotel_id=hotel_id, name=name, district="中心", nightly_price=300,
        lat=lat, lon=lon, supports_luggage_storage=storage,
        check_in_time="15:00", check_out_time="12:00")


def segment(value, start, end):
    return HotelSegment(value.hotel_id, value.name, start, end, value.nightly_price,
        value.supports_luggage_storage, value.check_in_time, value.check_out_time,
        value.lat, value.lon)


def switch_plan(*, storage=True, checkin="19:00", checkout="08:00", coords=True, transfer=35):
    a=hotel(1,"A");b=hotel(2,"B",storage=storage,lat=31.2 if coords else None,lon=121.2 if coords else None)
    nodes=[
        Node("hotel_checkout","A",checkout,f"{int(checkout[:2]):02d}:{int(checkout[3:])+15:02d}",metadata={"hotel_id":1,"lat":a.lat,"lon":a.lon}),
        Node("luggage_drop","B","08:50","09:20",transport_mode="public_transit",duration_min=transfer,
            metadata={"hotel_id":2,"lat":b.lat,"lon":b.lon,"previous_node":"A","luggage_action":"transfer","target_hotel_id":2}),
        Node("hotel_checkin","B",checkin,"19:30",metadata={"hotel_id":2,"lat":b.lat,"lon":b.lon}),
    ]
    plan=TripPlan("truth",[DayPlan(1,"2026-08-24","",[]),DayPlan(2,"2026-08-25","",nodes)],
        [segment(a,1,1),segment(b,2,2)],Budget())
    return plan


def codes(plan):
    req=Requirement(days=len(plan.days),start_date="2026-08-24",include_meals=False,
        lodging_strategy="flexible",max_hotel_changes=1)
    return {issue.code for issue in HardValidator(Config()).validate(plan,req)}


def test_storage_capability_and_hotel_time_constraints_are_hard_facts():
    assert not codes(switch_plan())
    assert "hotel_luggage_storage_unsupported" in codes(switch_plan(storage=False))
    assert "hotel_checkin_too_early" in codes(switch_plan(checkin="14:00"))
    assert "hotel_checkout_too_late" in codes(switch_plan(checkout="13:00"))


def test_early_checkout_and_late_checkin_are_legal():
    assert not codes(switch_plan(checkout="08:00",checkin="19:00"))


def test_hotel_transfer_is_one_canonical_transport_leg():
    plan=switch_plan(transfer=35)
    assert daily_transport_metrics(plan.days[1],Config(),"moderate").total_transport_min==35


def test_missing_target_coordinates_or_transport_fails_closed():
    assert "hotel_transfer_missing_transport" in codes(switch_plan(coords=False))
    assert "hotel_transfer_missing_transport" in codes(switch_plan(transfer=0))


def test_optimizer_uses_storage_capable_alternative_and_records_luggage_identity():
    a=hotel(1,"A");unsupported=hotel(2,"B",storage=False);supported=hotel(3,"C")
    days=[DayPlan(day,f"2026-08-{23+day:02d}","",[]) for day in range(1,5)]
    segments,decision=HotelOptimizer(MockMapClient(),Config()).optimize(days,[a,unsupported,supported],
        Requirement(days=4,lodging_strategy="flexible",max_hotel_changes=1,include_meals=False),250)
    drop=next(node for node in days[1].nodes if node.type=="luggage_drop")
    assert decision.action=="CHANGE" and segments[-1].hotel_id==3
    assert drop.metadata["source_hotel_id"]==1 and drop.metadata["target_hotel_id"]==3


def test_cross_day_start_must_match_previous_overnight_assignment():
    plan=switch_plan();b=plan.hotels[-1]
    plan.days.append(DayPlan(3,"2026-08-26","",[Node("attraction","P","09:00","10:00",metadata={"previous_node":"A"})]))
    b.end_day=3
    assert "hotel_assignment_discontinuity" in codes(plan)
    plan.days[-1].nodes[0].metadata["previous_node"]="B"
    assert "hotel_assignment_discontinuity" not in codes(plan)


def test_fixed_hotel_has_one_nightly_assignment_without_repeated_operations():
    a=hotel(1,"A")
    days=[DayPlan(day,f"2026-08-{23+day:02d}","",[]) for day in range(1,5)]
    segments,decision=HotelOptimizer(MockMapClient(),Config()).optimize(days,[a],Requirement(days=4),500)
    assert decision.action=="KEEP" and segments[0].start_day==1 and segments[0].end_day==4
    assert not [node for day in days for node in day.nodes if node.type in {"hotel_checkout","hotel_checkin"}]


def test_first_day_early_luggage_drop_can_precede_legal_evening_checkin():
    b=hotel(2,"B")
    nodes=[
        Node("luggage_drop","B","09:00","09:30",transport_mode="public_transit",duration_min=20,
            metadata={"hotel_id":2,"lat":b.lat,"lon":b.lon,"luggage_action":"drop","target_hotel_id":2}),
        Node("attraction","P","10:00","12:00",metadata={"opening_hours":{"weekly_hours":{"mon":["09:00","18:00"]}}}),
        Node("hotel_checkin","B","19:00","19:30",metadata={"hotel_id":2,"lat":b.lat,"lon":b.lon}),
    ]
    plan=TripPlan("arrival",[DayPlan(1,"2026-08-24","",nodes)],[segment(b,1,1)],Budget())
    assert not codes(plan)
