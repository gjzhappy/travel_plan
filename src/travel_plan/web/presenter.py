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


def present_plan(
    plan: dict[str, Any], version: int, requirement: dict[str, Any] | None = None,
    hotel_locations: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Add deterministic display copy while preserving the engine response."""
    result = {**plan, "version": version}
    result["days"] = [
        _present_day(day, plan.get("hotels", []), hotel_locations or {})
        for day in plan["days"]
    ]
    result["explanation"] = _explanation(plan)
    result["overview"] = _overview(plan, requirement or {})
    return result


def _overview(plan: dict[str, Any], requirement: dict[str, Any]) -> dict[str, Any]:
    """Translate existing requirement and plan facts into a first-screen summary."""
    party = requirement.get("party", {}) if isinstance(requirement.get("party"), dict) else {}
    adult, child = party.get("adult"), party.get("child")
    party_label = None
    if isinstance(adult, int) and isinstance(child, int):
        party_label = f"{adult} 成人" + (f" + {child} 儿童" if child else "")
    transport = {
        "public_transit": "公共交通优先", "walking": "步行优先", "driving": "驾车优先",
    }.get(requirement.get("transport"))
    lodging = {
        "fixed": "少换酒店", "flexible": "灵活安排住宿",
    }.get(requirement.get("lodging_strategy"))
    themes = [str(day.get("theme", "")).strip() for day in plan.get("days", [])]
    themes = list(dict.fromkeys(theme for theme in themes if theme))
    city = str(requirement.get("city") or "").strip()
    days = len(plan.get("days", []))
    title = f"{city}{days}日游" if city and days else "我的旅行方案"
    return {
        "title": title,
        "party": party_label,
        "transport": transport,
        "lodging": lodging,
        "budget": plan.get("budget", {}).get("total"),
        "route_features": themes,
    }


def _present_day(
    day: dict[str, Any], hotels: list[dict[str, Any]], hotel_locations: dict[int, dict[str, Any]]
) -> dict[str, Any]:
    """Create timeline and route DTOs without mutating or re-planning the day."""
    canonical = sorted(
        ({**node, "display": _node_display(node)} for node in day["nodes"]),
        key=lambda node: (node.get("start_time") or "99:99", node.get("end_time") or "99:99"),
    )
    timeline = _hotel_context(day, canonical, hotels, hotel_locations)
    route_nodes = []
    for node in timeline:
        metadata = node.get("metadata", {})
        if not _has_coordinates(metadata):
            continue
        if node.get("map_alias_of"):
            # The closing edge below points back to the single hotel marker.
            continue
        node_type = node.get("type", "")
        is_numbered = node_type in {"attraction", "lunch", "dinner"}
        display_order = 1 + sum(item["display_order"] is not None for item in route_nodes) if is_numbered else None
        route_nodes.append({
            "route_id": f"day-{day['day']}-node-{len(route_nodes) + 1}",
            "order": len(route_nodes) + 1,
            "display_order": display_order,
            "marker_label": str(display_order) if display_order is not None else "H",
            "marker_type": "hotel" if node_type.startswith("hotel_") else "activity",
            "type": node_type,
            "name": node.get("name", ""),
            "lat": metadata["lat"],
            "lng": metadata["lon"],
            "node_sequence": node.get("presentation_sequence"),
            "start_time": node.get("start_time"),
            "end_time": node.get("end_time"),
        })
    hotel_nodes = [node for node in route_nodes if node["marker_type"] == "hotel"]
    hotel_names = list(dict.fromkeys(node["name"] for node in hotel_nodes))
    if len(hotel_names) > 1:
        labels = {name: f"H{index}" for index, name in enumerate(hotel_names, 1)}
        for node in hotel_nodes:
            node["marker_label"] = labels[node["name"]]
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
            ] + ([{"from": route_nodes[-1]["order"], "to": route_nodes[0]["order"]}]
                 if timeline and timeline[-1].get("map_alias_of") and len(route_nodes) > 1 else []),
        },
        "summary": _day_summary(day),
    }


def _hotel_context(
    day: dict[str, Any], canonical: list[dict[str, Any]], hotels: list[dict[str, Any]],
    hotel_locations: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Expose the recorded hotel assignment as presentation context, never as a canonical node."""
    assigned = next(
        (hotel for hotel in hotels if hotel.get("start_day", 0) <= day["day"] <= hotel.get("end_day", 0)),
        None,
    )
    if not assigned:
        return [{**node, "presentation_sequence": index} for index, node in enumerate(canonical, 1)]
    types = {node.get("type") for node in canonical}
    location = hotel_locations.get(assigned.get("hotel_id"), {})
    metadata = ({"lat": location["lat"], "lon": location["lon"]}
                if _has_coordinates(location) else {})
    context = {
        "name": assigned.get("name", "住宿"), "start_time": "", "end_time": "",
        "duration_min": 0, "metadata": metadata,
        "presentation_derived": True, "presentation_source": "hotel_assignment",
    }
    before = [] if types & {"hotel_departure", "hotel_checkout"} else [
        {**context, "type": "hotel_departure", "display": _node_display({**context, "type": "hotel_departure"})}
    ]
    after = [] if types & {"hotel_return", "hotel_checkin"} else [
        {**context, "type": "hotel_return", "display": _node_display({**context, "type": "hotel_return"})}
    ]
    result = before + canonical + after
    # A fixed hotel is one visual identity but remains both ends of the route.
    # Re-use the departure sequence for the return so timeline/map interaction
    # stays truthful without drawing two markers at identical coordinates.
    if before and after and metadata:
        after[0]["map_alias_of"] = "hotel_departure"
    return [{**node, "presentation_sequence": index} for index, node in enumerate(result, 1)]


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
            "text": f"将 {names or '自由活动'} 组合在同一天，并按已有时间、路程与停留时长事实展示顺序。",
        })
    decision = plan.get("hotel_decision", {})
    reasons.append({
        "title": "住宿选择",
        "text": f"系统结论为 {decision.get('action', 'KEEP')}：{decision.get('reason', '优先减少行程折返')}。",
    })
    return reasons
