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
        "为什么选择这些地点", "为什么按这个顺序", "为什么在这个时间去",
        "为什么这样安排餐饮", "为什么这样安排住宿", "旅行节奏",
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
    assert reasons[0]["details"] == []
    assert reasons[2]["details"] == []
    assert all(not reason["available"] for reason in (reasons[0], reasons[2], reasons[3]))


def test_decision_evidence_connects_real_constraints_meal_and_hotel_facts():
    attraction = {"type": "attraction", "name": "西岸美术馆", "start_time": "14:20",
                  "end_time": "15:50", "duration_min": 8,
                  "metadata": {"category": "美术馆", "latest_entry_time": "16:30",
                               "closing_time": "17:00"}}
    meal = {"type": "dinner", "name": "本帮菜馆", "duration_min": 10,
            "metadata": {"detour_min": 11, "previous_node": "西岸美术馆",
                         "next_node": "人民广场酒店"}}
    plan = {"days": [{"day": 1, "theme": "艺术", "nodes": [attraction, meal]}],
            "hotels": [{"hotel_id": 3001, "name": "人民广场酒店", "start_day": 1, "end_day": 1}]}
    requirement = {"interests": ["美术馆"], "must_visit": ["西岸美术馆"]}

    reasons = build_explainability(plan, [], 1, requirement)["days"][0]["reasons"]
    text = " ".join(detail for reason in reasons for detail in reason["details"])

    assert "明确指定的必去地点" in text
    assert "满足 16:30 最晚入场要求" in text
    assert "仅增加约 11 分钟绕行" in text
    assert "避免额外换酒店和搬运行李" in text
    assert "已记录" not in text
    meal_reason = next(reason for reason in reasons if reason["category"] == "为什么这样安排餐饮")
    assert meal_reason["evidence"]["meals"][0]["detour_min"] == 11


def test_missing_detour_and_non_constraining_time_do_not_invent_explanations():
    plan = {"days": [{"day": 1, "theme": "自由", "nodes": [
        {"type": "attraction", "name": "公园", "start_time": "09:00", "end_time": "10:00", "metadata": {}},
        {"type": "lunch", "name": "餐厅", "metadata": {}},
    ]}]}
    reasons = build_explainability(plan, [], 1)["days"][0]["reasons"]
    assert not next(r for r in reasons if r["category"] == "为什么在这个时间去")["available"]
    assert not next(r for r in reasons if r["category"] == "为什么这样安排餐饮")["available"]
