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
    assert "开放时间" in result["explanation"][0]["text"]
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

    assert [node["order"] for node in route["nodes"]] == [1, 2]
    assert [node["node_sequence"] for node in route["nodes"]] == [1, 2]
    assert route["edges"] == [{"from": 1, "to": 2}]
