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
        _day_card(day, evidence_by_day.get(day.get("day"), {}), requirement or {})
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
            "route_score_label": "路线评分为既有 Planner 输出，仅用于展示。",
        },
        "days": days,
        "validator": _validator_card(validators),
        "review": _review_card(reviews, plan),
        "trace": [_trace_card(event) for event in current],
    }


def _day_card(
    day: dict[str, Any], evidence: dict[str, Any], requirement: dict[str, Any]
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
            "route_score": evidence.get("route_score", day.get("route_score", 0)),
            "travel_minutes": travel_minutes,
        },
        "evidence": [
            {"poi_id": poi_id, "name": names_by_id.get(poi_id, "未命名地点")}
            for poi_id in evidence_ids
        ],
        "source": "Evidence" if evidence else "WebPlanDTO",
        "reasons": [
            _requirement_reason(requirement, attractions),
            _route_reason(attractions, travel_minutes, evidence),
            _time_reason(attractions),
            _pace_reason(requirement),
        ],
    }


def _requirement_reason(requirement: dict[str, Any], attractions: list[dict[str, Any]]) -> dict[str, Any]:
    interests = [str(item) for item in requirement.get("interests", []) if item]
    must_visit = set(requirement.get("must_visit", []))
    matches = [node.get("name", "") for node in attractions if node.get("name") in must_visit]
    details = []
    if interests:
        details.append(f"用户兴趣：{'、'.join(interests)}")
    if matches:
        details.append(f"满足必去地点：{'、'.join(matches)}")
    return _reason("用户需求匹配", details, "Requirement")


def _route_reason(
    attractions: list[dict[str, Any]], travel_minutes: int, evidence: dict[str, Any]
) -> dict[str, Any]:
    details = []
    if attractions:
        details.append(f"按既有节点顺序串联 {len(attractions)} 处景点")
    if any(node.get("duration_min") is not None for node in attractions):
        details.append(f"已有交通时间合计：{travel_minutes} 分钟")
    if "route_score" in evidence:
        details.append(f"既有路线评分：{float(evidence['route_score']):.1f}")
    return _reason("路线原因", details, "Route Plan / Transport Result")


def _time_reason(attractions: list[dict[str, Any]]) -> dict[str, Any]:
    details = []
    if attractions and all(node.get("start_time") and node.get("end_time") for node in attractions):
        details.append("已记录每个景点的开始、结束与游玩时长")
    if attractions and all(node.get("metadata", {}).get("opening_hours") for node in attractions):
        details.append("已记录景点开放时间")
    if any(node.get("metadata", {}).get("latest_entry_time") for node in attractions):
        details.append("已记录最晚入场时间")
    return _reason("时间约束", details, "Validator / POI facts")


def _pace_reason(requirement: dict[str, Any]) -> dict[str, Any]:
    pace = requirement.get("pace")
    return _reason("节奏原因", [f"用户节奏偏好：{pace}"] if pace else [], "Requirement")


def _reason(category: str, details: list[str], source: str) -> dict[str, Any]:
    return {"category": category, "details": details or ["暂无数据"], "available": bool(details), "source": source}


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
