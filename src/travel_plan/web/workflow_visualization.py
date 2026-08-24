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
    ("requirement_refinement", "重新理解调整需求", "Requirement Refinement", "feedback", "根据审核反馈提取新的调整约束，保持用户原始意图不被覆盖"),
    ("scoped_replanner", "调整不可行安排", "Scoped Replanner", "feedback", "根据调整范围重新规划不可行部分，避免全量重算"),
    ("feedback_validator", "再次验证", "Hard Validator", "feedback", "再次检查调整后的安排是否满足时间、交通和开放条件"),
    ("output", "生成旅行方案", "Final Plan", "output", "整理最终行程、地图和解释信息"),
)

EVENT_NODE_IDS = {
    "WORKFLOW_STARTED": "input", "AGENT_COMPLETED": "requirement",
    "PLAN_GENERATED": "planner", "VALIDATOR_PASSED": "validator",
    "VALIDATOR_BLOCKED": "validator", "REPLAN_COMPLETED": "scoped_replanner",
    "REVIEW_COMPLETED": "review", "REVIEW_FAILED": "review",
    "REQUIREMENT_REFINEMENT_STARTED": "requirement_refinement",
    "REQUIREMENT_REFINEMENT_COMPLETED": "requirement_refinement",
    "SCOPED_REPLAN_STARTED": "scoped_replanner",
    "SCOPED_REPLAN_COMPLETED": "scoped_replanner",
    "PLAN_VERSION_SAVED": "output",
    "WORKFLOW_COMPLETED": "output",
    "QUALITY_REVIEW_BLOCKED": "output",
}
STAGE_NODE_IDS = {
    "REQUIREMENT": "requirement", "RETRIEVAL": "retrieval", "PLANNER": "planner",
    "ROUTE_PLAN": "route", "ROUTE_PLANNING": "route", "MEAL_PLANNING": "meal",
    "HOTEL_PLANNING": "hotel", "VALIDATOR": "validator", "VALIDATE": "validator",
    "HARD_VALIDATION": "feedback_validator", "FINAL_VALIDATION": "feedback_validator",
    "REVIEW": "review", "REQUIREMENT_REFINEMENT": "requirement_refinement",
    "SCOPED_REPLANNER": "scoped_replanner", "SCOPED_REPLAN": "scoped_replanner",
}


def workflow_node_id(event: dict[str, Any]) -> str | None:
    """Return an explicit event/node association without guessing from time."""
    event_type = str(event.get("event_type") or "").upper()
    if event_type in EVENT_NODE_IDS:
        return EVENT_NODE_IDS[event_type]
    if event_type in {"STAGE_STARTED", "STAGE_COMPLETED", "STAGE_FAILED"}:
        stage = str(event.get("stage") or event.get("details", {}).get("stage") or "").upper()
        return STAGE_NODE_IDS.get(stage)
    return None

# Presentation coordinates describe the architecture without changing its execution.
# Columns form the main trunk; rows expose fan-out and the validation/replan loop.
LAYOUT = {
    "input": (2, 1), "requirement": (2, 2),
    "retrieval": (2, 3), "facts": (2, 4), "constraints": (4, 3),
    "planner": (2, 5), "route": (2, 6), "meal": (4, 5), "hotel": (4, 6),
    "validator": (2, 7), "repair": (4, 7), "review": (2, 8),
    "requirement_refinement": (7, 8), "scoped_replanner": (7, 9),
    "feedback_validator": (7, 10), "output": (2, 11),
}

PHASES = (
    ("main", "主流程", 1, 5),
    ("feedback", "反馈优化闭环", 6, 9),
)

EDGES = (
    ("input", "requirement", "", "normal"), ("requirement", "retrieval", "", "normal"),
    ("requirement", "constraints", "分支", "normal"), ("retrieval", "facts", "", "normal"),
    ("facts", "planner", "", "normal"), ("constraints", "planner", "", "normal"),
    ("planner", "route", "", "normal"), ("planner", "meal", "", "normal"),
    ("planner", "hotel", "", "normal"), ("route", "validator", "", "normal"),
    ("meal", "validator", "", "normal"), ("hotel", "validator", "", "normal"),
    ("validator", "review", "通过", "normal"), ("validator", "repair", "失败", "repair"),
    ("repair", "validator", "复检", "repair"), ("review", "output", "通过", "normal"),
    ("review", "requirement_refinement", "反馈", "feedback"),
    ("requirement_refinement", "scoped_replanner", "修正", "feedback"),
    ("scoped_replanner", "feedback_validator", "验证", "feedback"),
    ("feedback_validator", "output", "通过", "feedback"),
)

EDGE_TOOLTIPS = {
    ("review", "requirement_refinement"): "审核反馈优化闭环",
    ("requirement_refinement", "scoped_replanner"): "按重新理解的需求修正安排",
    ("scoped_replanner", "feedback_validator"): "再次验证调整后的方案",
    ("feedback_validator", "output"): "输出优化后的方案",
}


def _event_payload(event: dict[str, Any]) -> dict[str, Any]:
    """Return presentation-safe event facts from either raw or streamed traces."""
    return event.get("details") or event


def workflow_graph(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Map only observable execution facts to node states; never infer progress."""
    state = {node[0]: "pending" for node in NODES}
    metadata: dict[str, dict[str, Any]] = {}
    recorded_durations: dict[str, int | float] = {}
    stage_nodes = {stage: (node,) for stage, node in STAGE_NODE_IDS.items()}
    observed_types: set[str] = set()
    review_advisory = False
    refinement_completed = False
    scoped_replan_completed = False
    for event in events:
        stage = str(event.get("stage") or event.get("details", {}).get("stage") or "").upper()
        status = str(event.get("status") or "").upper()
        event_type = str(event.get("event_type") or "").upper()
        payload = _event_payload(event)
        observed_types.add(event_type)
        linked_node = workflow_node_id(event)
        if linked_node:
            metadata.setdefault(linked_node, {})["event_type"] = event_type
        nodes = stage_nodes.get(stage, ())
        mapped = "running" if status == "RUNNING" or event_type == "STAGE_STARTED" else "completed"
        if status in {"FAILED", "ERROR"} or event_type == "STAGE_FAILED": mapped = "failed"
        if event_type == "VALIDATOR_BLOCKED":
            state["validator"] = "failed"
        elif event_type == "REPLAN_COMPLETED":
            state["scoped_replanner"] = "completed"
        else:
            for node in nodes: state[node] = mapped
        if event.get("duration_ms") is not None:
            for node in nodes:
                metadata.setdefault(node, {})["duration_ms"] = event["duration_ms"]
            # One trace duration is one measured stage, even when that stage is
            # represented by several presentation nodes.
            recorded_durations[stage or event_type] = event["duration_ms"]
        if event_type == "WORKFLOW_STARTED": state["input"] = "completed"
        if event_type == "PLAN_GENERATED": state["planner"] = "completed"
        if event_type == "PLAN_VERSION_SAVED": state["output"] = "completed"
        if event_type == "WORKFLOW_COMPLETED": state["output"] = "completed"
        if event_type == "QUALITY_REVIEW_BLOCKED": state["output"] = "failed"
        failed_review_event = event_type == "REVIEW_FAILED" or (
            event_type == "REVIEW_COMPLETED" and payload.get("passed") is False
        )
        if failed_review_event:
            # The Review Agent executed successfully. ``passed=false`` is a
            # business advisory that can trigger refinement, not a failed
            # stage lifecycle or evidence that refinement has started.
            review_advisory = True
            state["review"] = "completed"
        if stage == "REQUIREMENT_REFINEMENT" and mapped == "completed":
            refinement_completed = True
        if event_type in {"REPLAN_COMPLETED", "SCOPED_REPLAN_COMPLETED"} or (
            stage == "SCOPED_REPLAN" and mapped == "completed"
        ):
            scoped_replan_completed = True
            state["scoped_replanner"] = "completed"
            state["feedback_validator"] = "running"
            metadata.setdefault("scoped_replanner", {})["event_type"] = event_type
        elif scoped_replan_completed and stage in {"HARD_VALIDATION", "FINAL_VALIDATION"}:
            state["feedback_validator"] = mapped
            metadata.setdefault("feedback_validator", {})["event_type"] = event_type
            if event.get("duration_ms") is not None:
                metadata["feedback_validator"]["duration_ms"] = event["duration_ms"]
    counts = {status: sum(value == status for value in state.values())
              for status in ("completed", "running", "pending", "failed")}
    active = next((key for key, value in state.items() if value == "running"), None)

    def edge_execution_status(source: str, target: str, edge_type: str) -> str:
        if edge_type == "normal":
            if state[target] == "running":
                return "active"
            return "executed" if state[target] in {"completed", "failed"} else "available"
        if edge_type == "repair":
            if source == "validator" and state["repair"] == "running":
                return "active"
            observed = ("VALIDATOR_BLOCKED" in observed_types if source == "validator"
                        else {"VALIDATOR_BLOCKED", "VALIDATOR_PASSED"} <= observed_types)
            return "executed" if observed else "available"
        if source == "review":
            if "REQUIREMENT_REFINEMENT_STARTED" in observed_types:
                return "active"
            return "executed" if review_advisory else "available"
        if source == "requirement_refinement":
            if "SCOPED_REPLAN_STARTED" in observed_types:
                return "active"
            return "executed" if refinement_completed else "available"
        if source == "scoped_replanner":
            return "executed" if scoped_replan_completed else "available"
        return "executed" if state["output"] == "completed" else "available"

    return {
        "nodes": [{"id": key, "node_id": key, "label": display_name, "display_name": display_name,
                   "technical_label": technical, "description": description,
                   "kind": kind, "phase": kind, "status": state[key],
                   "layout": {"column": LAYOUT[key][0], "row": LAYOUT[key][1]},
                   **metadata.get(key, {})}
                  for key, display_name, technical, kind, description in NODES],
        "edges": [{"from": source, "to": target, "label": label,
                   "show_label": False,
                   "tooltip": EDGE_TOOLTIPS.get((source, target), label),
                   "edge_label_position": {"position": "middle", "offset": 10},
                   "edge_type": edge_type,
                   "execution_status": edge_execution_status(source, target, edge_type)}
                  for source, target, label, edge_type in EDGES],
        "notice": "流程图同时展示架构能力与 Event Trace 记录的真实执行路径；不改变工作流，也不展示模型思考过程。",
        "phases": [{"id": key, "label": label, "column_start": start, "column_end": end}
                   for key, label, start, end in PHASES],
        "summary": {"active_node_id": active, "counts": counts,
                    "recorded_duration_ms": sum(recorded_durations.values()),
                    "startup_status": "STARTED" if any(
                        str(event.get("event_type", "")).upper() == "WORKFLOW_STARTED"
                        for event in events) else "WAITING_START"},
    }
