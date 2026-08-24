from travel_plan.web.presenter import present_plan


def test_present_plan_adds_display_fields_without_planning():
    plan = {
        "trip_id": "trip_web",
        "days": [{"day": 1, "date": "2026-09-01", "theme": "建筑", "route_score": 42.5,
                  "nodes": [{"type": "attraction", "name": "外滩", "start_time": "09:00",
                             "end_time": "10:30", "duration_min": 20,
                             "metadata": {"category": "建筑", "lat": 31.24, "lon": 121.49}}]}],
        "hotels": [], "budget": {"total": 0},
        "hotel_decision": {"action": "KEEP", "reason": "换酒店收益不足"},
    }

    result = present_plan(plan, 3)

    assert result["version"] == 3
    assert result["days"][0]["summary"] == {"attraction_count": 1, "travel_minutes": 20}
    assert result["days"][0]["nodes"][0]["display"]["detail"] == "建筑 · 建议停留 90 分钟"
    assert "路线评分" not in result["explanation"][0]["text"]
    assert "display" not in plan["days"][0]["nodes"][0]


def test_timeline_sorts_meals_and_hotel_nodes_by_start_time():
    nodes = [
        {"type": "dinner", "name": "晚餐", "start_time": "18:30", "end_time": "20:00", "metadata": {}},
        {"type": "attraction", "name": "美术馆", "start_time": "13:30", "end_time": "15:30", "metadata": {}},
        {"type": "hotel_checkin", "name": "上海酒店", "start_time": "20:30", "end_time": "21:00", "metadata": {}},
        {"type": "lunch", "name": "午餐", "start_time": "12:00", "end_time": "13:00", "metadata": {}},
    ]
    plan = {"days": [{"day": 1, "date": "2026-09-01", "theme": "艺术", "nodes": nodes}],
            "hotels": [], "budget": {}, "hotel_decision": {}}

    timeline = present_plan(plan, 1)["days"][0]["timeline"]

    assert [node["type"] for node in timeline] == ["lunch", "attraction", "dinner", "hotel_checkin"]
    assert timeline[-1]["display"]["type_label"] == "酒店入住"


def test_route_visualization_has_order_sequence_and_edges():
    nodes = [
        {"type": "attraction", "name": "东方明珠", "start_time": "09:00", "end_time": "11:00", "metadata": {"lat": 31.24, "lon": 121.50}},
        {"type": "lunch", "name": "午餐", "start_time": "12:00", "end_time": "13:00", "metadata": {"lat": 0, "lon": 0}},
        {"type": "attraction", "name": "浦东美术馆", "start_time": "13:30", "end_time": "15:00", "metadata": {"lat": 31.25, "lon": 121.51}},
    ]
    plan = {"days": [{"day": 1, "date": "2026-09-01", "theme": "艺术", "nodes": nodes}],
            "hotels": [], "budget": {}, "hotel_decision": {}}

    route = present_plan(plan, 1)["days"][0]["route_visualization"]

    assert [node["order"] for node in route["nodes"]] == [1, 2, 3]
    assert [node["display_order"] for node in route["nodes"]] == [1, 2, 3]
    assert [node["node_sequence"] for node in route["nodes"]] == [1, 2, 3]
    assert route["edges"] == [{"from": 1, "to": 2}, {"from": 2, "to": 3}]


def test_fixed_hotel_assignment_frames_timeline_without_inventing_time_or_coordinates():
    plan = {
        "days": [{"day": 1, "date": "2026-09-01", "theme": "城市", "nodes": [
            {"type": "attraction", "name": "外滩", "start_time": "09:00", "end_time": "10:00", "metadata": {"lat": 31.2, "lon": 121.4}},
        ]}],
        "hotels": [{"name": "上海酒店", "start_day": 1, "end_day": 1}],
        "budget": {}, "hotel_decision": {},
    }

    day = present_plan(plan, 1)["days"][0]

    assert [node["type"] for node in day["timeline"]] == ["hotel_departure", "attraction", "hotel_return"]
    assert day["timeline"][0]["presentation_source"] == "hotel_assignment"
    assert day["timeline"][0]["start_time"] == ""
    assert [node["name"] for node in day["route_visualization"]["nodes"]] == ["外滩"]


def test_canonical_hotel_change_order_and_coordinate_contract_are_preserved():
    nodes = [
        {"type": "hotel_checkin", "name": "新酒店", "start_time": "20:00", "end_time": "20:30", "metadata": {"lat": 31.3, "lon": 121.5}},
        {"type": "attraction", "name": "景点", "start_time": "10:00", "end_time": "12:00", "metadata": {"lat": 31.2, "lon": 121.4}},
        {"type": "luggage_drop", "name": "新酒店", "start_time": "08:15", "end_time": "08:45", "metadata": {}},
        {"type": "hotel_checkout", "name": "原酒店", "start_time": "08:00", "end_time": "08:15", "metadata": {"lat": 31.1, "lon": 121.3}},
    ]
    plan = {"days": [{"day": 2, "date": "2026-09-02", "theme": "换酒店", "nodes": nodes}],
            "hotels": [{"name": "新酒店", "start_day": 2, "end_day": 3}], "budget": {}, "hotel_decision": {}}

    day = present_plan(plan, 1)["days"][0]

    assert [node["type"] for node in day["timeline"]] == ["hotel_checkout", "luggage_drop", "attraction", "hotel_checkin"]
    assert all(not node.get("presentation_derived") for node in day["timeline"])
    assert [(node["lat"], node["lng"]) for node in day["route_visualization"]["nodes"]] == [(31.1, 121.3), (31.2, 121.4), (31.3, 121.5)]
    assert [node["marker_label"] for node in day["route_visualization"]["nodes"]] == ["H", "1", "H"]
