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
