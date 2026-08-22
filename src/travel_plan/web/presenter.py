"""Pure presentation helpers; no planning decisions belong in this module."""

from typing import Any


TYPE_LABELS = {
    "attraction": "景点",
    "lunch": "午餐",
    "dinner": "晚餐",
    "hotel_departure": "从酒店出发",
    "hotel_return": "返回酒店",
    "hotel_checkin": "酒店入住",
    "hotel_checkout": "酒店退房",
    "luggage_drop": "寄存行李",
}


def present_plan(plan: dict[str, Any], version: int) -> dict[str, Any]:
    """Add deterministic display copy while preserving the engine response."""
    result = {**plan, "version": version}
    result["days"] = [_present_day(day) for day in plan["days"]]
    result["explanation"] = _explanation(plan)
    return result


def _present_day(day: dict[str, Any]) -> dict[str, Any]:
    """Create timeline and route DTOs without mutating or re-planning the day."""
    timeline = sorted(
        ({**node, "display": _node_display(node)} for node in day["nodes"]),
        key=lambda node: (node.get("start_time") or "99:99", node.get("end_time") or "99:99"),
    )
    route_nodes = []
    for node in timeline:
        metadata = node.get("metadata", {})
        if node.get("type") != "attraction" or not _has_coordinates(metadata):
            continue
        route_nodes.append({
            "order": len(route_nodes) + 1,
            "name": node.get("name", ""),
            "lat": metadata["lat"],
            "lng": metadata["lon"],
            "node_sequence": len(route_nodes) + 1,
        })
    return {
        **day,
        # ``nodes`` remains available for API compatibility; timeline is the
        # explicit presentation contract consumed by new renderers.
        "nodes": timeline,
        "timeline": timeline,
        "route_visualization": {
            "nodes": route_nodes,
            "edges": [
                {"from": previous["order"], "to": current["order"]}
                for previous, current in zip(route_nodes, route_nodes[1:])
            ],
        },
        "summary": _day_summary(day),
    }


def _has_coordinates(metadata: dict[str, Any]) -> bool:
    return all(isinstance(metadata.get(key), (int, float)) for key in ("lat", "lon"))


def _node_display(node: dict[str, Any]) -> dict[str, str]:
    metadata = node.get("metadata", {})
    label = TYPE_LABELS.get(node["type"], node["type"])
    if node["type"] == "attraction":
        detail = f"{metadata.get('category', '城市体验')} · 建议停留 {_minutes(node)}"
    elif node["type"] in {"lunch", "dinner"}:
        detail = f"{metadata.get('cuisine', '本地风味')} · 人均 ¥{metadata.get('price_per_person', 0):g}"
    else:
        detail = label
    return {"type_label": label, "detail": detail}


def _minutes(node: dict[str, Any]) -> str:
    start_h, start_m = map(int, node["start_time"].split(":"))
    end_h, end_m = map(int, node["end_time"].split(":"))
    return f"{(end_h * 60 + end_m) - (start_h * 60 + start_m)} 分钟"


def _day_summary(day: dict[str, Any]) -> dict[str, Any]:
    attractions = [node for node in day["nodes"] if node["type"] == "attraction"]
    travel = sum(node.get("duration_min", 0) for node in day["nodes"])
    return {"attraction_count": len(attractions), "travel_minutes": travel}


def _explanation(plan: dict[str, Any]) -> list[dict[str, str]]:
    reasons = []
    for day in plan["days"]:
        attractions = [node for node in day["nodes"] if node["type"] == "attraction"]
        names = "、".join(node["name"] for node in attractions)
        reasons.append({
            "title": f"第 {day['day']} 天 · {day['theme']}",
            "text": f"将 {names or '自由活动'} 组合在同一天，并按开放时间、路程与停留时长排定顺序。路线评分 {day.get('route_score', 0):.1f}。",
        })
    decision = plan.get("hotel_decision", {})
    reasons.append({
        "title": "住宿选择",
        "text": f"系统结论为 {decision.get('action', 'KEEP')}：{decision.get('reason', '优先减少行程折返')}。",
    })
    return reasons
