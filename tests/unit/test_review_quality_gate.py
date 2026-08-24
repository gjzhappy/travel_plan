from pathlib import Path
import json

import pytest

from travel_plan.errors import QualityReviewBlocked
from travel_plan.main import build_workflow
from travel_plan.models.requirement import Party, Requirement
from travel_plan.models.review import ReviewIssue, ReviewResult
from travel_plan.agents.review_agent import ReviewAgent
from travel_plan.observability.trace_reader import TraceReader
from travel_plan.planning.review_constraints import compile_review_constraints


def test_too_tiring_compiles_all_and_only_affected_days():
    req = Requirement(days=3, party=Party(2, 1))
    review = ReviewResult(False, [
        ReviewIssue("DAY", "too_tiring", "busy", 3),
        ReviewIssue("DAY", "too_tiring", "busy", 1),
        ReviewIssue("DAY", "unknown", "unknown", 2),
    ], [])
    compiled, affected, changes = compile_review_constraints(req, review)
    assert affected == [1, 3]
    assert compiled.day_constraints == {
        1: {"max_attractions": 4}, 3: {"max_attractions": 4}
    }
    assert [change["day"] for change in changes] == [1, 3]
    assert req.day_constraints == {}


def test_constraint_merge_does_not_fake_a_second_diff():
    req = Requirement(days=1, pace="relaxed", day_constraints={1: {"max_attractions": 3}})
    review = ReviewResult(False, [ReviewIssue("DAY", "too_tiring", "busy", 1)], [])
    compiled, _, changes = compile_review_constraints(req, review)
    assert compiled.day_constraints[1]["max_attractions"] == 3
    assert changes == []


def test_day_constraints_survive_json_round_trip_for_every_affected_day():
    req = Requirement(days=4, pace="relaxed")
    review = ReviewResult(False, [
        ReviewIssue("DAY", "too_tiring", "busy", day) for day in (2, 3, 4)
    ], [])
    compiled, affected, _ = compile_review_constraints(req, review)
    restored = Requirement.from_dict(json.loads(json.dumps(compiled.to_dict())))
    assert affected == [2, 3, 4]
    assert sorted(restored.day_constraints) == [2, 3, 4]


def test_review_repairs_all_affected_days_and_projects_trace(tmp_path):
    workflow = build_workflow(Path.cwd(), tmp_path)
    original_review = ReviewAgent().review
    review_calls = []

    def review(req, plan, evidence):
        review_calls.append({day.day: sum(node.type == "attraction" for node in day.nodes)
                             for day in plan.days})
        if len(review_calls) == 1:
            return ReviewResult(False, [
                ReviewIssue("DAY", "too_tiring", "busy", day) for day in (2, 3, 4)
            ], [])
        result = original_review(req, plan, evidence)
        assert not [issue for issue in result.issues
                    if issue.type == "too_tiring" and issue.day in {2, 3, 4}]
        return ReviewResult(True, [], [])

    workflow.reviewer.review = review
    original_plan_day = workflow.route.plan_day
    replans = []

    def plan_day(pois, req, hotel, day_number, required_poi_ids=None):
        incoming = req.day_constraints[day_number]["max_attractions"]
        result = original_plan_day(pois, req, hotel, day_number, required_poi_ids)
        replans.append((day_number, incoming, len(pois),
                        sum(node.type == "attraction" for node in result.nodes)))
        return result

    workflow.route.plan_day = plan_day
    plan, state, _ = workflow.execute(
        "上海4天，2位成人，节奏不要太赶，公共交通优先，午餐和晚餐都需要安排。",
        "multi_day_review",
    )

    assert [item[0] for item in replans] == [2, 3, 4]
    assert all(item[3] <= item[1] for item in replans)
    assert all(review_calls[1][day] <= replans[index][1]
               for index, day in enumerate((2, 3, 4)))
    final_issues = original_review(
        Requirement.from_dict(state.requirements),
        __import__("travel_plan.workflow", fromlist=["_plan_from_dict"])._plan_from_dict(plan),
    ).issues
    assert not [issue for issue in final_issues
                if issue.type == "too_tiring" and issue.day in {2, 3, 4}]

    events = TraceReader(tmp_path).read("multi_day_review", state.version)
    compiled = next(event for event in events
                    if event.event_type == "REVIEW_CONSTRAINTS_COMPILED")
    replan_event = next(event for event in events
                        if event.event_type == "STAGE_COMPLETED"
                        and event.payload.get("stage") == "SCOPED_REPLAN")
    assert compiled.payload["affected_days"] == [2, 3, 4]
    assert sorted(map(int, compiled.payload["day_constraints"])) == [2, 3, 4]
    assert replan_event.payload["affected_days"] == [2, 3, 4]
    assert replan_event.payload["target_day"] is None
    assert any(event.event_type == "PLAN_VERSION_SAVED" for event in events)
    assert events[-1].event_type == "PLAN_VERSION_SAVED"

    story = TraceReader(tmp_path).planning_story_projection("multi_day_review", state.version)
    repair = next(item for item in story if item["stage"] == "SCOPED_REPLAN")
    assert "2、3、4" in repair["title"]
    graph = TraceReader(tmp_path).workflow_projection("multi_day_review", state.version)
    node = next(item for item in graph["nodes"] if item["id"] == "scoped_replanner")
    assert node["affected_days"] == [2, 3, 4]


def test_unknown_failed_review_blocks_persist_and_review_stage_completed(tmp_path):
    workflow = build_workflow(Path.cwd(), tmp_path)
    workflow.reviewer.review = lambda req, plan, evidence: ReviewResult(
        False, [ReviewIssue("GLOBAL", "unknown", "unsupported")], []
    )
    with pytest.raises(QualityReviewBlocked):
        workflow.execute("上海一日游", "quality_blocked")
    assert workflow.state.load("quality_blocked") is None
    path = tmp_path / "quality_blocked" / "events.jsonl"
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert any(event["event_type"] == "REVIEW_COMPLETED" and event["details"]["passed"] is False
               for event in events)
    assert events[-1]["event_type"] == "QUALITY_REVIEW_BLOCKED"
    assert not any(event["event_type"] == "PLAN_VERSION_SAVED" for event in events)
