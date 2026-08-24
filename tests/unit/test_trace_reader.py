import json

import pytest

from travel_plan.observability import TraceReader, TraceReadError


def write_trace(root, trip_id, events):
    path = root / trip_id / "events.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("\n".join(json.dumps(event) for event in events) + "\n", encoding="utf-8")


def test_reader_normalizes_existing_trace_and_builds_timeline(tmp_path):
    write_trace(
        tmp_path,
        "trip-1",
        [
            {
                "sequence": 1,
                "trip_id": "trip-1",
                "plan_version": 2,
                "parent_version": 1,
                "event_type": "REPLAN_COMPLETED",
                "actor": "replanner",
                "details": {"scope": "DAY", "trigger_review_number": 3},
            }
        ],
    )

    reader = TraceReader(tmp_path)
    event = reader.read("trip-1")[0]
    assert event.event_id == 1
    assert event.payload == {"scope": "DAY", "trigger_review_number": 3}
    assert event.trigger_review_number == 3
    assert reader.render("trip-1") == (
        '#1 v2 [REPLAN_COMPLETED] replanner: scope="DAY", trigger_review_number=3'
    )


def test_reader_is_empty_for_missing_trace_and_does_not_create_files(tmp_path):
    reader = TraceReader(tmp_path)
    assert reader.read("unknown") == []
    assert reader.timeline("unknown") == []
    assert reader.render("unknown") == ""
    assert list(tmp_path.iterdir()) == []


def test_reader_reports_corrupt_line_with_location(tmp_path):
    path = tmp_path / "broken" / "events.jsonl"
    path.parent.mkdir()
    path.write_text("not-json\n", encoding="utf-8")

    with pytest.raises(TraceReadError, match=r"events\.jsonl:1"):
        TraceReader(tmp_path).read("broken")


def test_reader_rejects_cross_trip_event(tmp_path):
    write_trace(
        tmp_path,
        "requested",
        [
            {
                "sequence": 1,
                "trip_id": "another",
                "plan_version": 1,
                "parent_version": None,
                "event_type": "WORKFLOW_STARTED",
                "actor": "workflow",
                "details": {},
            }
        ],
    )

    with pytest.raises(TraceReadError, match="does not match"):
        TraceReader(tmp_path).read("requested")


def test_historical_graph_projection_is_trace_only_and_version_isolated(tmp_path):
    write_trace(tmp_path, "history", [
        {"sequence": 1, "trip_id": "history", "plan_version": 1,
         "parent_version": None, "event_type": "STAGE_COMPLETED", "actor": "meal-planner",
         "details": {"stage": "MEAL_PLANNING", "duration_ms": 37}},
        {"sequence": 2, "trip_id": "history", "plan_version": 2,
         "parent_version": 1, "event_type": "STAGE_COMPLETED", "actor": "replanner",
         "details": {"stage": "SCOPED_REPLAN", "scope": "DAY", "iteration": 1}},
    ])

    reader = TraceReader(tmp_path)
    version_one = {node["id"]: node for node in reader.workflow_projection("history", 1)["nodes"]}
    version_two = {node["id"]: node for node in reader.workflow_projection("history", 2)["nodes"]}

    assert version_one["meal"]["status"] == "completed"
    assert version_one["meal"]["duration_ms"] == 37
    assert version_one["scoped_replanner"]["status"] == "pending"
    assert version_two["meal"]["status"] == "pending"
    assert version_two["scoped_replanner"]["status"] == "completed"


def test_historical_story_projection_is_version_isolated_and_preserves_duration_truth(tmp_path):
    write_trace(tmp_path, "story-history", [
        {"sequence": 1, "trip_id": "story-history", "plan_version": 1,
         "parent_version": None, "event_type": "STAGE_STARTED", "actor": "review-agent",
         "details": {"stage": "REVIEW", "review_number": 1}},
        {"sequence": 2, "trip_id": "story-history", "plan_version": 1,
         "parent_version": None, "event_type": "REVIEW_COMPLETED", "actor": "review-agent",
         "details": {"passed": False, "issues": [{"scope": "DAY", "day": 2, "type": "pace", "message": "节奏偏紧"}], "duration_ms": 42}},
        {"sequence": 3, "trip_id": "story-history", "plan_version": 2,
         "parent_version": 1, "event_type": "STAGE_COMPLETED", "actor": "replanner",
         "details": {"stage": "SCOPED_REPLAN", "scope": "DAY", "target_day": 2}},
    ])
    reader = TraceReader(tmp_path)
    v1 = reader.planning_story_projection("story-history", 1)
    v2 = reader.planning_story_projection("story-history", 2)
    assert [item["stage"] for item in v1] == ["REVIEW"]
    assert v1[0]["status"] == "advisory"
    assert [item["stage"] for item in v2] == ["SCOPED_REPLAN"]
    # Story pacing is separate; the technical event keeps its measured duration.
    assert reader.read("story-history", 1)[1].payload["duration_ms"] == 42
