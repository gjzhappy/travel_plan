from travel_plan.config import Config
from travel_plan.models.requirement import Requirement
from travel_plan.models.trip import Budget, DayPlan, Node, TripPlan
from travel_plan.validation.validator import HardValidator


def plan_with(nodes):
    return TripPlan("test", [DayPlan(1, "2026-08-19", "", nodes)], [], Budget())


def test_unexplained_afternoon_gap_is_fail_closed():
    nodes = [
        Node("lunch", "lunch", "12:00", "13:00", metadata={"opening_hours": hours()}),
        Node("dinner", "dinner", "18:00", "19:00", metadata={"opening_hours": hours()}),
    ]
    issues = HardValidator(Config()).validate(plan_with(nodes), Requirement(include_meals=True))
    assert "unreasonable_idle_gap" in {issue.code for issue in issues}


def test_hotel_or_user_rest_explains_idle_gap():
    for explanation in (
        Node("hotel_checkin", "hotel", "14:00", "14:30"),
        Node("attraction", "rest", "14:00", "14:30", metadata={"user_requested_rest": True, "opening_hours": hours()}),
    ):
        nodes = [explanation, Node("dinner", "dinner", "18:00", "19:00", metadata={"opening_hours": hours()})]
        issues = HardValidator(Config()).validate(plan_with(nodes), Requirement(include_meals=False))
        assert "unreasonable_idle_gap" not in {issue.code for issue in issues}


def hours():
    return {"weekly_hours": {day: ["08:00", "22:00"] for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}, "special_dates": {}}
