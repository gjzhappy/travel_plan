"""Deterministic, read-only projection of trace facts into a user planning story."""

from typing import Any

STAGES = {
    "REQUIREMENT": ("理解旅行需求", "正在整理旅行目标、偏好和限制条件…", "已理解本次旅行需求。"),
    "RETRIEVAL": ("查找适合地点", "正在从地点库筛选候选地点…", "已筛选符合条件的候选地点。"),
    "PLANNER": ("生成初版路线", "正在生成每日行程框架…", "已生成每日行程框架。"),
    "ROUTE_PLANNING": ("安排行程顺序", "正在比较路线顺序与交通衔接…", "已生成每日活动顺序和交通衔接。"),
    "HOTEL_PLANNING": ("安排住宿衔接", "正在结合路线安排住宿…", "住宿已加入每日路线衔接。"),
    "MEAL_PLANNING": ("安排餐饮", "正在结合路线安排餐饮…", "餐饮已加入每日路线衔接。"),
    "VALIDATOR": ("检查方案可行性", "正在检查时间、开放时间和交通约束…", "时间、开放时间和交通约束检查完成。"),
    "REQUIREMENT_REFINEMENT": ("根据审核调整规划要求", "正在把审核意见转为调整范围…", "已根据审核意见更新规划要求。"),
    "SCOPED_REPLAN": ("调整部分行程", "正在局部重新规划…", "局部行程已重新规划。"),
    "HARD_VALIDATION": ("再次检查", "正在检查调整后的行程…", "调整后的行程可执行。"),
    "FINAL_VALIDATION": ("最终检查", "正在进行最终可行性检查…", "最终可行性检查通过。"),
}

def _scope_text(scope: str | None, day: Any = None) -> str:
    if str(scope or "").upper() == "DAY" and day:
        return f"仅调整第 {day} 天的规划约束。"
    return {"NODE": "仅调整相关行程节点。", "MEAL": "仅调整餐饮安排。", "GLOBAL": "重新调整整体行程约束。"}.get(str(scope or "").upper(), "")

def _day_list(days: list[Any]) -> str:
    return "、".join(str(day) for day in days)

def planning_story(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate lifecycle events; heartbeats and generic events add no row."""
    story, positions, occurrences, active = [], {}, {}, {}
    def put(key, item):
        if key in positions: story[positions[key]].update(item)
        else: positions[key] = len(story); story.append(item)
    for event in events:
        event_type = str(event.get("event_type", "")).upper()
        stage, status = str(event.get("stage", "")).upper(), str(event.get("status", "")).upper()
        if event_type in {"AGENT_HEARTBEAT", "WORKFLOW_STARTED"}: continue
        if event_type == "QUALITY_REVIEW_BLOCKED":
            put(("QUALITY_REVIEW_BLOCKED", 1), {
                "id": "quality-review-blocked", "stage": "QUALITY_REVIEW_BLOCKED",
                "node_id": "output", "title": "未生成最终方案", "status": "failed",
                "detail": event.get("message") or "行程虽然在时间上可执行，但体验审核仍认为安排过于紧凑。",
                "issues": (event.get("last_review") or {}).get("issues", []),
            })
            continue
        stage = {"AGENT_COMPLETED": "REQUIREMENT", "PLAN_GENERATED": "PLANNER", "VALIDATOR_PASSED": "VALIDATOR", "VALIDATOR_BLOCKED": "VALIDATOR", "PLAN_VERSION_SAVED": "PERSIST"}.get(event_type, stage)
        if stage == "REVIEW" or event_type == "REVIEW_COMPLETED":
            stage = "REVIEW"
            if event_type == "STAGE_STARTED": occurrences[stage] = occurrences.get(stage, 0) + 1; active[stage] = occurrences[stage]
            number = active.get(stage, occurrences.get(stage, 1))
            item = {"id": f"review-{number}", "stage": stage, "node_id": "review", "title": "行程体验审核" if number <= 1 else "再次体验审核"}
            if event_type == "REVIEW_COMPLETED":
                issues, passed = event.get("issues") or [], event.get("passed") is True
                item.update(status="completed" if passed else "advisory", detail="整体安排合理，可以进入最终检查。" if passed else (f"发现 {len(issues)} 个可以进一步优化的地方。" if issues else "发现可以进一步优化的地方。"), issues=[{k: issue.get(k) for k in ("day", "scope", "type", "message") if issue.get(k) not in (None, "")} for issue in issues])
            else: item.update(status="running", detail="正在检查路线节奏、交通负担和整体游览体验…", issues=[])
            put((stage, number), item); continue
        if stage not in STAGES and stage != "PERSIST": continue
        if event_type == "STAGE_STARTED": occurrences[stage] = occurrences.get(stage, 0) + 1; active[stage] = occurrences[stage]
        number = active.get(stage, occurrences.get(stage, 1))
        title, running, complete = ("旅行方案已生成", "正在保存旅行方案…", "旅行方案已生成并保存。") if stage == "PERSIST" else STAGES[stage]
        failed = status in {"FAILED", "ERROR"} or event_type == "STAGE_FAILED"
        state = "failed" if failed else ("running" if event_type == "STAGE_STARTED" or status == "RUNNING" else "completed")
        detail = running if state == "running" else ("执行失败。" if failed else complete)
        affected_days = event.get("affected_days") or []
        scope = (_scope_text(event.get("scope"), event.get("target_day"))
                 if len(affected_days) <= 1 else
                 f"根据体验审核结果，对第 {_day_list(affected_days)} 天进行了局部调整。")
        if scope and stage in {"REQUIREMENT_REFINEMENT", "SCOPED_REPLAN"}: detail = scope if state != "running" else f"{detail} {scope}"
        if stage == "SCOPED_REPLAN" and len(affected_days) > 1:
            title = f"正在调整第 {_day_list(affected_days)} 天行程" if state == "running" else f"第 {_day_list(affected_days)} 天已重新规划"
        elif stage == "SCOPED_REPLAN" and event.get("target_day"):
            title = f"调整第 {event['target_day']} 天行程" if state == "running" else f"第 {event['target_day']} 天已重新规划"
        put((stage, number), {"id": f"{stage.lower()}-{number}", "stage": stage, "node_id": event.get("workflow_node_id"), "title": title, "status": state, "detail": detail, "issues": []})
    return story
