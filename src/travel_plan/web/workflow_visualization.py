"""Read-only runtime workflow graph derived from persisted/streamed events."""

from typing import Any


NODES = (
    ("input", "输入", "User Requirement", "input"),
    ("requirement", "需求理解", "Requirement Agent", "agent"),
    ("retrieval", "知识召回", "Semantic Retrieval", "retrieval"),
    ("facts", "事实补全", "SQLite Facts", "retrieval"),
    ("constraints", "约束解析", "Constraint Parsing", "retrieval"),
    ("planner", "行程规划", "Planning Engine", "planning"),
    ("route", "路线优化", "Route Planner", "planning"),
    ("meal", "餐饮安排", "Meal Planner", "planning"),
    ("hotel", "住宿优化", "Hotel Optimizer", "planning"),
    ("validator", "可行性检查", "Hard Validator", "validation"),
    ("repair", "局部重规划", "Code Repair / Scoped Replan", "replan"),
    ("review", "体验审核", "Review Agent", "review"),
    ("output", "生成结果", "Final Plan", "output"),
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
        if event_type == "PLAN_VERSION_SAVED": state["output"] = "completed"
        if event_type == "WORKFLOW_COMPLETED": state["output"] = "completed"
    return {
        "nodes": [{"id": key, "label": label, "technical_label": technical,
                   "kind": kind, "status": state[key], **metadata.get(key, {})}
                  for key, label, technical, kind in NODES],
        "edges": [{"from": source, "to": target, "label": label}
                  for source, target, label in EDGES],
        "notice": "流程图展示工作流执行状态，不展示模型思考过程。",
    }
