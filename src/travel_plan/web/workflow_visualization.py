"""Read-only runtime workflow graph derived from persisted/streamed events."""

from typing import Any


NODES = (
    ("input", "提交旅行需求", "User Requirement", "input", "接收你的旅行目标、偏好和限制条件"),
    ("requirement", "理解旅行需求", "Requirement Agent", "agent", "AI正在分析你的旅行目标、偏好和限制条件"),
    ("retrieval", "寻找合适景点", "Retrieval Service", "retrieval", "根据兴趣和旅行条件召回候选地点"),
    ("facts", "补充景点信息", "Fact Enrichment", "retrieval", "补充开放时间、位置、游玩时长等信息"),
    ("constraints", "整理旅行限制", "Constraint Parsing", "retrieval", "整理预算、时间和出行偏好等限制条件"),
    ("planner", "编排行程框架", "Planning Engine", "planning", "将候选地点组织为可执行的每日行程"),
    ("route", "优化每日路线", "Route Planner", "planning", "根据距离、时间和交通方式安排访问顺序"),
    ("meal", "安排餐饮", "Meal Planner", "planning", "结合行程位置和偏好安排午餐、晚餐"),
    ("hotel", "安排住宿", "Hotel Optimizer", "planning", "综合位置、预算和换酒店成本选择住宿方案"),
    ("validator", "检查方案可行性", "Hard Validator", "validation", "检查时间、开放时间、交通和约束条件"),
    ("repair", "调整不可行安排", "Code Repair / Scoped Replan", "replan", "仅对未通过检查的行程部分进行调整"),
    ("review", "体验审核", "Review Agent", "review", "从游客体验角度检查方案质量"),
    ("output", "生成旅行方案", "Final Plan", "output", "整理最终行程、地图和解释信息"),
)

# Presentation coordinates describe the architecture without changing its execution.
# Columns form the main trunk; rows expose fan-out and the validation/replan loop.
LAYOUT = {
    "input": (1, 2), "requirement": (2, 2),
    "retrieval": (3, 1), "facts": (4, 1), "constraints": (4, 3),
    "planner": (5, 2), "route": (6, 1), "meal": (6, 2), "hotel": (6, 3),
    "validator": (7, 2), "repair": (7, 4), "review": (8, 2), "output": (9, 2),
}

PHASES = (
    ("understand", "需求理解", 1, 2),
    ("prepare", "信息准备", 3, 4),
    ("plan", "行程编排", 5, 6),
    ("assure", "质量校验", 7, 8),
    ("deliver", "方案交付", 9, 9),
)

EDGES = (
    ("input", "requirement", ""), ("requirement", "retrieval", ""),
    ("requirement", "constraints", "分支"), ("retrieval", "facts", ""),
    ("facts", "planner", ""), ("constraints", "planner", ""),
    ("planner", "route", ""), ("planner", "meal", ""),
    ("planner", "hotel", ""), ("route", "validator", ""),
    ("meal", "validator", ""), ("hotel", "validator", ""),
    ("validator", "review", "通过"), ("validator", "repair", "失败"),
    ("repair", "validator", "复检"), ("review", "output", "通过"),
    ("review", "repair", "需调整"),
)


def workflow_graph(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Map only observable execution facts to node states; never infer progress."""
    state = {node[0]: "pending" for node in NODES}
    state["input"] = "completed"
    metadata: dict[str, dict[str, Any]] = {}
    recorded_durations: dict[str, int | float] = {}
    stage_nodes = {
        "REQUIREMENT": ("requirement",), "RETRIEVAL": ("retrieval", "facts", "constraints"),
        "PLANNER": ("planner", "route", "meal", "hotel"),
        "ROUTE_PLAN": ("planner", "route", "meal", "hotel"),
        "VALIDATOR": ("validator",), "VALIDATE": ("validator",), "REVIEW": ("review",),
    }
    for event in events:
        stage = str(event.get("stage") or event.get("details", {}).get("stage") or "").upper()
        status = str(event.get("status") or "").upper()
        event_type = str(event.get("event_type") or "").upper()
        nodes = stage_nodes.get(stage, ())
        mapped = "running" if status == "RUNNING" or event_type == "STAGE_STARTED" else "completed"
        if status in {"FAILED", "ERROR"}: mapped = "failed"
        if event_type == "VALIDATOR_BLOCKED":
            state["validator"] = "failed"; state["repair"] = "running"
        elif event_type == "REPLAN_COMPLETED":
            state["repair"] = "completed"
        else:
            for node in nodes: state[node] = mapped
        if event.get("duration_ms") is not None:
            for node in nodes: metadata[node] = {"duration_ms": event["duration_ms"]}
            # One trace duration is one measured stage, even when that stage is
            # represented by several presentation nodes.
            recorded_durations[stage or event_type] = event["duration_ms"]
        if event_type == "PLAN_VERSION_SAVED": state["output"] = "completed"
        if event_type == "WORKFLOW_COMPLETED": state["output"] = "completed"
    counts = {status: sum(value == status for value in state.values())
              for status in ("completed", "running", "pending", "failed")}
    active = next((key for key, value in state.items() if value == "running"), None)
    return {
        "nodes": [{"id": key, "label": display_name, "display_name": display_name,
                   "technical_label": technical, "description": description,
                   "kind": kind, "status": state[key],
                   "layout": {"column": LAYOUT[key][0], "row": LAYOUT[key][1]},
                   **metadata.get(key, {})}
                  for key, display_name, technical, kind, description in NODES],
        "edges": [{"from": source, "to": target, "label": label}
                  for source, target, label in EDGES],
        "notice": "流程图展示工作流执行状态，不展示模型思考过程。",
        "phases": [{"id": key, "label": label, "column_start": start, "column_end": end}
                   for key, label, start, end in PHASES],
        "summary": {"active_node_id": active, "counts": counts,
                    "recorded_duration_ms": sum(recorded_durations.values())},
    }
