from travel_plan.web.planning_story import planning_story


def event(event_type, stage, status="COMPLETED", **facts):
    return {"event_type": event_type, "stage": stage, "status": status, **facts}


def test_story_filters_heartbeat_and_updates_lifecycle_row():
    story = planning_story([
        event("WORKFLOW_STARTED", "WORKFLOW", "RUNNING"),
        *[event("AGENT_HEARTBEAT", "REVIEW", "RUNNING") for _ in range(5)],
        event("STAGE_STARTED", "ROUTE_PLANNING", "RUNNING"),
        event("STAGE_COMPLETED", "ROUTE_PLANNING", duration_ms=42),
    ])
    assert len(story) == 1
    assert story[0]["title"] == "安排行程顺序"
    assert story[0]["status"] == "completed"


def test_review_advisory_uses_only_real_issue_and_drives_scoped_loop_story():
    story = planning_story([
        event("STAGE_STARTED", "REVIEW", "RUNNING", review_number=1),
        event("REVIEW_COMPLETED", "REVIEW", passed=False, issues=[
            {"day": 2, "scope": "DAY", "type": "pace", "message": "两个活动之间衔接偏紧"}
        ]),
        event("STAGE_STARTED", "REQUIREMENT_REFINEMENT", "RUNNING", iteration=1),
        event("STAGE_COMPLETED", "REQUIREMENT_REFINEMENT", scope="DAY", target_day=2),
        event("STAGE_STARTED", "SCOPED_REPLAN", "RUNNING", scope="DAY", target_day=2),
        event("STAGE_COMPLETED", "SCOPED_REPLAN", scope="DAY", target_day=2),
        event("STAGE_STARTED", "HARD_VALIDATION", "RUNNING", iteration=1),
        event("STAGE_COMPLETED", "HARD_VALIDATION", passed=True, duration_ms=42),
    ])
    assert [item["status"] for item in story] == ["advisory", "completed", "completed", "completed"]
    assert story[0]["issues"] == [{"day": 2, "scope": "DAY", "type": "pace", "message": "两个活动之间衔接偏紧"}]
    assert "第 2 天" in story[1]["detail"]
    assert story[2]["title"] == "第 2 天已重新规划"


def test_multi_day_review_replan_story_reports_every_affected_day():
    story = planning_story([
        event("STAGE_STARTED", "SCOPED_REPLAN", "RUNNING", scope="DAY",
              target_day=None, affected_days=[2, 3, 4]),
        event("STAGE_COMPLETED", "SCOPED_REPLAN", scope="DAY",
              target_day=None, affected_days=[2, 3, 4]),
    ])
    assert story[0]["title"] == "第 2、3、4 天已重新规划"
    assert "第 2、3、4 天" in story[0]["detail"]


def test_review_pass_has_no_fake_issue_and_missing_issue_stays_generic():
    passed = planning_story([event("STAGE_STARTED", "REVIEW", "RUNNING"), event("REVIEW_COMPLETED", "REVIEW", passed=True, issues=[])])
    assert passed[0]["status"] == "completed" and passed[0]["issues"] == []
    advisory = planning_story([event("STAGE_STARTED", "REVIEW", "RUNNING"), event("REVIEW_COMPLETED", "REVIEW", passed=False)])
    assert advisory[0]["detail"] == "发现可以进一步优化的地方。"
    assert "交通" not in advisory[0]["detail"]
