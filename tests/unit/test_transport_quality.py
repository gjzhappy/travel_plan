from types import SimpleNamespace

from travel_plan.config import Config
from travel_plan.models.requirement import Requirement
from travel_plan.models.trip import Budget, DayPlan, Node, TripPlan
from travel_plan.planning.scoring import route_score
from travel_plan.planning.transport_quality import (
    daily_transport_metrics, excess_transport_penalty, policy_for,
)
from travel_plan.validation.validator import HardValidator


def leg(name, minutes, source="test_matrix", node_type="attraction", **metadata):
    return Node(node_type, name, "09:00", "10:00", transport_mode="metro",
                duration_min=minutes, metadata={"transport_source": source, **metadata})


def scored(priority, total, largest, pace="relaxed"):
    policy=policy_for(Config(),pace)
    return route_score(priority,total,0,0,0,0,excess_transport_penalty(total,largest,policy))


def test_excess_penalty_selects_normal_route_over_small_priority_gain():
    assert scored(100,90,30) > scored(104,250,70)


def test_normal_priority_tradeoff_does_not_become_nearest_neighbor():
    assert scored(130,110,40) > scored(100,90,30)


def test_single_long_leg_is_elevated_even_when_total_is_preferred():
    day=DayPlan(1,"2026-08-24","",[leg("A",10),leg("B",80)])
    metrics=daily_transport_metrics(day,Config(),"relaxed")
    assert metrics.total_transport_min==90 and metrics.largest_transfer_min==80
    assert metrics.quality_status=="elevated" and metrics.long_transfer_count==1


def test_canonical_legs_are_summed_once_without_next_travel_metadata():
    day=DayPlan(1,"2026-08-24","",[
        leg("A",20,next_travel_min=30),leg("B",30,next_travel_min=10),
        leg("Hotel",10,node_type="hotel_return",hotel_related=True),
    ])
    metrics=daily_transport_metrics(day,Config(),"relaxed")
    assert metrics.total_transport_min==60 and metrics.transport_leg_count==3


def test_fallback_source_and_estimated_duration_remain_on_leg():
    day=DayPlan(1,"2026-08-24","",[leg("A",64,source="rule_estimate")])
    metrics=daily_transport_metrics(day,Config(),"relaxed")
    assert day.nodes[0].metadata["transport_source"]=="rule_estimate"
    assert metrics.total_transport_min==64


def test_hard_gate_reports_structured_excess_and_must_visit_exception():
    day=DayPlan(1,"2026-08-24","",[leg("A",130),leg("B",120)])
    plan=TripPlan("x",[day],[],Budget())
    issue=next(i for i in HardValidator(Config()).validate(plan,Requirement(include_meals=False,pace="relaxed")) if i.code=="excessive_daily_transport")
    assert issue.details["total_transport_min"]==250
    assert issue.details["largest_transfer_min"]==130
    day.nodes[0].metadata["must_visit_related"]=True
    day.nodes[1].metadata["must_visit"]=True
    assert "excessive_daily_transport" not in {i.code for i in HardValidator(Config()).validate(plan,Requirement(include_meals=False,pace="relaxed"))}


def test_relaxed_policy_is_stricter_than_intensive():
    assert policy_for(Config(),"relaxed").hard_total_min < policy_for(Config(),"intensive").hard_total_min
