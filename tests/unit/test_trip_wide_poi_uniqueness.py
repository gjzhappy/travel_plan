from types import SimpleNamespace

from travel_plan.config import Config
from travel_plan.models.requirement import Requirement
from travel_plan.models.trip import Budget, DayPlan, Node, TripPlan
from travel_plan.validation.repair import CodeRepair
from travel_plan.validation.validator import HardValidator
from travel_plan.workflow import TravelWorkflow


def attraction(poi_id, name=None):
    return Node("attraction", name or f"poi-{poi_id}", "09:00", "10:00", poi_id)


def plan(*days):
    return TripPlan("trip", [DayPlan(index + 1, "2026-08-24", "", nodes) for index, nodes in enumerate(days)], [], Budget())


def candidates(*poi_ids):
    return [SimpleNamespace(poi_id=poi_id) for poi_id in poi_ids]


def test_day_scope_excludes_attractions_from_unaffected_days_by_poi_id():
    current = plan([attraction(100)], [attraction(200)], [attraction(300)])

    result, required = TravelWorkflow._scoped_candidates(
        current, candidates(100, 200, 400), Requirement(), "DAY", 2
    )

    assert [item.poi_id for item in result] == [200, 400]
    assert required == set()


def test_node_scope_protects_other_nodes_on_same_day_and_other_days():
    current = plan([attraction(100)], [attraction(200), attraction(201)])

    result, _ = TravelWorkflow._scoped_candidates(
        current, candidates(100, 200, 201, 400), Requirement(), "NODE", 2, "200"
    )

    assert [item.poi_id for item in result] == [200, 400]


def test_global_replan_candidates_are_not_filtered_against_old_plan():
    # GLOBAL deliberately bypasses _scoped_candidates and replans from retrieval.
    current = plan([attraction(100)])
    shortlist = candidates(100, 200)

    assert [item.poi_id for item in shortlist] == [100, 200]
    assert current.days[0].nodes[0].poi_id == 100


def test_must_visit_is_preserved_only_when_affected_day_owned_it():
    requirement = Requirement(must_visit=["上海迪士尼"], resolved_must_visit=[{
        "source_text": "上海迪士尼", "poi_id": 1046, "canonical_name": "上海迪士尼乐园"
    }])
    current = plan([attraction(1046, "上海迪士尼乐园")], [attraction(200)])

    other_day, other_required = TravelWorkflow._scoped_candidates(
        current, candidates(1046, 200, 300), requirement, "DAY", 2
    )
    must_day, must_required = TravelWorkflow._scoped_candidates(
        current, candidates(1046, 200, 300), requirement, "DAY", 1
    )

    assert 1046 not in {item.poi_id for item in other_day}
    assert other_required == set()
    assert 1046 in {item.poi_id for item in must_day}
    assert must_required == {1046}


def test_validator_hard_fails_duplicate_attraction_without_touching_plan():
    current = plan([attraction(100)], [attraction(100)])
    requirement = Requirement(include_meals=False)

    issues = HardValidator(Config()).validate(current, requirement)
    duplicate = next(issue for issue in issues if issue.code == "duplicate_trip_poi")
    repaired = CodeRepair().repair(current, [duplicate], requirement)

    assert duplicate.details == {"poi_id": 100, "days": [1, 2]}
    assert [day.nodes[0].poi_id for day in repaired.days] == [100, 100]


def test_validator_does_not_apply_attraction_rule_to_hotel_or_meal_nodes():
    repeated_hotel = Node("hotel_return", "人民广场酒店", "20:00", "20:10", 777)
    repeated_meal = Node("lunch", "餐厅", "12:00", "13:00", 888)
    current = plan([repeated_hotel, repeated_meal], [repeated_hotel, repeated_meal])

    codes = {issue.code for issue in HardValidator(Config()).validate(current, Requirement(include_meals=False))}

    assert "duplicate_trip_poi" not in codes
