"""Deterministic view models for the explainability presentation layer.

This module only translates facts that already exist in a plan and its event
trace.  It deliberately has no dependency on planners, providers, or agents.
"""

from __future__ import annotations

from typing import Any


SOURCE_LABELS = {
    "WebPlanDTO": "行程结果",
    "Evidence": "规划证据",
    "Event Trace": "事件记录",
    "Review Result": "体验审核",
    "Validator Result": "硬约束校验",
}


def build_explainability(
    plan: dict[str, Any], events: list[dict[str, Any]], version: int,
    requirement: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a stable, read-only explanation snapshot from recorded facts."""
    current = [event for event in events if event.get("plan_version") == version]
    evidence_by_day = {
        item.get("day"): item for item in plan.get("evidence", []) if isinstance(item, dict)
    }
    days = [
        _day_card(day, evidence_by_day.get(day.get("day"), {}), requirement or {}, plan)
        for day in plan.get("days", [])
    ]
    validators = [event for event in current if event.get("actor") == "validator"]
    reviews = [event for event in current if event.get("event_type") == "REVIEW_COMPLETED"]

    return {
        "schema_version": "1.0",
        "plan_version": version,
        "notice": "解释仅展示已有规划事实，不参与景点选择、路线、时间安排或校验。",
        "sources": [
            {"key": key, "label": label, "available": _source_available(key, plan, current)}
            for key, label in SOURCE_LABELS.items()
        ],
        "overview": {
            "day_count": len(days),
            "attraction_count": sum(item["facts"]["attraction_count"] for item in days),
            "evidence_count": len(plan.get("evidence", [])),
        },
        "days": days,
        "validator": _validator_card(validators),
        "review": _review_card(reviews, plan),
        "trace": [_trace_card(event) for event in current],
    }


def _day_card(
    day: dict[str, Any], evidence: dict[str, Any], requirement: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    attractions = [node for node in day.get("nodes", []) if node.get("type") == "attraction"]
    evidence_ids = list(evidence.get("poi_ids", []))
    names_by_id = {node.get("poi_id"): node.get("name") for node in attractions}
    travel_minutes = sum(node.get("duration_min", 0) or 0 for node in day.get("nodes", []))
    return {
        "day": day.get("day"),
        "title": f"第 {day.get('day')} 天 · {day.get('theme', '')}",
        "facts": {
            "attraction_count": len(attractions),
            "attractions": [node.get("name", "") for node in attractions],
            "travel_minutes": travel_minutes,
        },
        "evidence": [
            {"poi_id": poi_id, "name": names_by_id.get(poi_id, "未命名地点")}
            for poi_id in evidence_ids
        ],
        "source": "Evidence" if evidence else "WebPlanDTO",
        "reasons": _decision_reasons(day, attractions, requirement, evidence, plan)[:6],
    }


def _requirement_reason(requirement: dict[str, Any], attractions: list[dict[str, Any]]) -> dict[str, Any]:
    interests = [str(item) for item in requirement.get("interests", []) if item]
    required_ids = {item["poi_id"] for item in requirement.get("resolved_must_visit", [])}
    must_visit = set(requirement.get("must_visit", []))
    matches = [node.get("name", "") for node in attractions
               if node.get("poi_id") in required_ids or node.get("name") in must_visit]
    details = []
    categories = {str(node.get("metadata", {}).get("category", "")) for node in attractions}
    matched_interests = [interest for interest in interests if interest in categories]
    if matched_interests:
        details.append(f"这些地点与{'、'.join(matched_interests)}偏好相符")
    if matches:
        details.append(f"{'、'.join(matches)}是你明确指定的必去地点")
    return _reason("为什么选择这些地点", details, "Requirement", {
        "interests": matched_interests, "must_visit": matches,
    })


def _route_reason(
    attractions: list[dict[str, Any]], travel_minutes: int, evidence: dict[str, Any]
) -> dict[str, Any]:
    details = []
    if attractions:
        pairs = [f"{a.get('name')} → {b.get('name')}" for a, b in zip(attractions, attractions[1:])]
        if pairs:
            details.append(f"按 {'、'.join(pairs)} 连续游览，避免打乱已验证的交通衔接")
    return _reason("为什么按这个顺序", details, "Route Plan / Transport Result", {
        "route_order": [node.get("name") for node in attractions],
        "recorded_travel_minutes": travel_minutes,
        "evidence_poi_ids": evidence.get("poi_ids", []),
    })


def _time_reason(attractions: list[dict[str, Any]]) -> dict[str, Any]:
    details = []
    evidence = []
    for node in attractions:
        metadata = node.get("metadata", {})
        start, end = node.get("start_time"), node.get("end_time")
        latest, closing = metadata.get("latest_entry_time"), metadata.get("closing_time")
        if start and end and latest and start <= latest:
            message = f"{node.get('name')}安排在 {start} 到达，满足 {latest} 最晚入场要求"
            if closing and end <= closing:
                message += f"，并可在 {closing} 闭馆前完成游览"
            details.append(message)
            evidence.append({"name": node.get("name"), "arrival": start, "end": end,
                             "latest_entry": latest, "closing": closing})
    return _reason("为什么在这个时间去", details, "Validator / POI facts", {"constraints": evidence})


def _pace_reason(requirement: dict[str, Any]) -> dict[str, Any]:
    pace = requirement.get("pace")
    return _reason("旅行节奏", [f"行程按你选择的“{pace}”节奏组织每日活动"] if pace else [],
                   "Requirement", {"pace": pace} if pace else {})


def _meal_reason(day: dict[str, Any]) -> dict[str, Any]:
    details, evidence = [], []
    for node in day.get("nodes", []):
        if node.get("type") not in {"lunch", "dinner"}:
            continue
        meta = node.get("metadata", {})
        detour = meta.get("detour_min")
        if isinstance(detour, (int, float)):
            previous, following = meta.get("previous_node"), meta.get("next_node")
            between = f"，衔接 {previous} 与 {following}" if previous and following else ""
            details.append(f"{node.get('name')}仅增加约 {detour:g} 分钟绕行{between}")
            evidence.append({"name": node.get("name"), "detour_min": detour,
                             "previous": previous, "next": following})
    return _reason("为什么这样安排餐饮", details, "Meal Plan", {"meals": evidence})


def _hotel_reason(day: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    nodes = day.get("nodes", [])
    types = {node.get("type") for node in nodes}
    hotels = [h for h in plan.get("hotels", [])
              if h.get("start_day", 0) <= day.get("day", 0) <= h.get("end_day", 0)]
    if {"hotel_checkout", "hotel_checkin"} <= types:
        luggage = any(node.get("type") == "luggage_drop" for node in nodes)
        if luggage:
            return _reason("为什么这样安排住宿", ["本日换酒店，并在游览前完成行李处理，避免携带行李进入后续景点"],
                           "Hotel / Itinerary", {"switch": True, "luggage_node": True})
    if hotels:
        name = hotels[0].get("name", "酒店")
        return _reason("为什么这样安排住宿", [f"当天从{name}出发并返回同一酒店，避免额外换酒店和搬运行李"],
                       "Hotel Assignment", {"switch": False, "hotel_id": hotels[0].get("hotel_id")})
    return _reason("为什么这样安排住宿", [], "Hotel Assignment", {})


def _decision_reasons(day, attractions, requirement, evidence, plan):
    return [
        _requirement_reason(requirement, attractions),
        _route_reason(attractions, sum(n.get("duration_min", 0) or 0 for n in day.get("nodes", [])), evidence),
        _time_reason(attractions), _meal_reason(day), _hotel_reason(day, plan), _pace_reason(requirement),
    ]


def _reason(category: str, details: list[str], source: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {"category": category, "details": details, "available": bool(details),
            "source": source, "evidence": evidence}


def _validator_card(events: list[dict[str, Any]]) -> dict[str, Any]:
    if not events:
        return {"status": "UNAVAILABLE", "stage": None, "issues": [], "source": "Validator Result"}
    final = next((e for e in reversed(events) if e.get("payload", {}).get("stage") == "FINAL_GATE"), events[-1])
    issues = final.get("payload", {}).get("issues", [])
    return {
        "status": "PASSED" if final.get("event_type") == "VALIDATOR_PASSED" else "BLOCKED",
        "stage": final.get("payload", {}).get("stage"),
        "issues": issues if isinstance(issues, list) else [],
        "event_id": final.get("event_id"),
        "source": "Validator Result",
    }


def _review_card(events: list[dict[str, Any]], plan: dict[str, Any]) -> dict[str, Any]:
    if not events:
        return {"status": "UNAVAILABLE", "issues": [], "source": "Review Result"}
    final = events[-1]
    payload = final.get("payload", {})
    issues = payload.get("issues", plan.get("remaining_issues", []))
    return {
        "status": "PASSED" if payload.get("passed") else "ADVISORY",
        "review_number": payload.get("review_number"),
        "issues": issues if isinstance(issues, list) else [],
        "event_id": final.get("event_id"),
        "source": "Review Result",
    }


def _trace_card(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": event.get("event_id"),
        "event_type": event.get("event_type"),
        "actor": event.get("actor"),
        "payload": event.get("payload", {}),
        "source": "Event Trace",
    }


def _source_available(source: str, plan: dict[str, Any], events: list[dict[str, Any]]) -> bool:
    if source == "WebPlanDTO":
        return bool(plan)
    if source == "Evidence":
        return bool(plan.get("evidence"))
    if source == "Event Trace":
        return bool(events)
    if source == "Review Result":
        return any(event.get("event_type") == "REVIEW_COMPLETED" for event in events)
    return any(event.get("actor") == "validator" for event in events)
