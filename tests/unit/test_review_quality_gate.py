from pathlib import Path
import json

import pytest

from travel_plan.errors import QualityReviewBlocked
from travel_plan.main import build_workflow
from travel_plan.models.requirement import Party, Requirement
from travel_plan.models.review import ReviewIssue, ReviewResult
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
