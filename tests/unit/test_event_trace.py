import json
from datetime import datetime
from pathlib import Path

from travel_plan.main import build_workflow


def read_events(root, trip_id):
    path = root / trip_id / "events.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_workflow_records_versioned_agent_review_validator_trace(tmp_path):
    workflow = build_workflow(Path.cwd(), tmp_path)
    workflow.execute("上海一日游", "trace_trip")
    events = read_events(tmp_path, "trace_trip")

    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert all(event["plan_version"] == 1 and event["parent_version"] is None for event in events)
    assert ("AGENT_COMPLETED", "requirement-agent") in {
        (event["event_type"], event["actor"]) for event in events
    }
    assert any(event["event_type"] == "REVIEW_COMPLETED" for event in events)
    assert any(event["event_type"] == "VALIDATOR_PASSED" for event in events)
    assert events[-1]["event_type"] == "PLAN_VERSION_SAVED"


def test_event_write_failure_does_not_change_workflow(tmp_path, monkeypatch):
    workflow = build_workflow(Path.cwd(), tmp_path)

    def fail(*args, **kwargs):
        raise OSError("trace unavailable")

    monkeypatch.setattr(Path, "open", fail)
    # EventTrace catches the failure. Restoring Path.open before state persistence
    # isolates this assertion from the state manager's separate file writes.
    monkeypatch.undo()
    monkeypatch.setattr(workflow.events, "_next_sequence", fail)
    plan, state, _ = workflow.execute("上海一日游", "trace_failure")
    assert plan["trip_id"] == "trace_failure"
    assert state.version == 1


def test_trace_notifies_subscriber_with_timestamp(tmp_path):
    workflow = build_workflow(Path.cwd(), tmp_path)
    observed = []
    workflow.events.subscribe(observed.append)

    workflow.execute("上海一日游", "live_trace")

    assert [event.sequence for event in observed] == list(range(1, len(observed) + 1))
    assert observed[0].event_type == "WORKFLOW_STARTED"
    assert datetime.fromisoformat(observed[0].timestamp).tzinfo is not None
    stages = {event.details.get("stage") for event in observed}
    assert {"REQUIREMENT", "RETRIEVAL", "PLANNER", "VALIDATOR", "REVIEW"} <= stages
