from travel_plan.web.explainability import build_explainability


def test_explainability_uses_only_plan_and_recorded_events():
    plan = {
        "days": [{"day": 1, "theme": "建筑", "route_score": 9.5, "nodes": [
            {"type": "attraction", "poi_id": 7, "name": "外滩", "duration_min": 12},
        ]}],
        "evidence": [{"day": 1, "poi_ids": [7], "route_score": 9.5}],
        "remaining_issues": [],
    }
    events = [
        {"event_id": 1, "plan_version": 2, "event_type": "VALIDATOR_PASSED", "actor": "validator",
         "payload": {"stage": "FINAL_GATE", "issues": []}},
        {"event_id": 2, "plan_version": 2, "event_type": "REVIEW_COMPLETED", "actor": "review-agent",
         "payload": {"review_number": 1, "passed": True, "issues": []}},
        {"event_id": 3, "plan_version": 1, "event_type": "VALIDATOR_BLOCKED", "actor": "validator",
         "payload": {"stage": "FINAL_GATE", "issues": [{"message": "old"}]}},
    ]

    result = build_explainability(plan, events, 2)

    assert result["days"][0]["evidence"] == [{"poi_id": 7, "name": "外滩"}]
    assert result["validator"]["status"] == "PASSED"
    assert result["review"]["status"] == "PASSED"
    assert [item["event_id"] for item in result["trace"]] == [1, 2]
    assert "不参与" in result["notice"]
    assert [reason["category"] for reason in result["days"][0]["reasons"]] == [
        "用户需求匹配", "路线原因", "时间约束", "节奏原因",
    ]


def test_explainability_marks_missing_optional_sources_without_inventing_results():
    result = build_explainability({"days": []}, [], 1)

    assert result["validator"]["status"] == "UNAVAILABLE"
    assert result["review"]["status"] == "UNAVAILABLE"
    assert {item["key"]: item["available"] for item in result["sources"]} == {
        "WebPlanDTO": True,
        "Evidence": False,
        "Event Trace": False,
        "Review Result": False,
        "Validator Result": False,
    }
    assert result["days"] == []


def test_explainability_reports_missing_evidence_instead_of_inventing_it():
    plan = {"days": [{"day": 1, "theme": "自由活动", "nodes": []}]}

    result = build_explainability(plan, [], 1, {})

    reasons = result["days"][0]["reasons"]
    assert reasons[0]["details"] == ["暂无数据"]
    assert reasons[2]["details"] == ["暂无数据"]
    assert all(not reason["available"] for reason in (reasons[0], reasons[2], reasons[3]))
