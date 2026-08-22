import json

import pytest
import travel_plan.workflow as workflow_module
from travel_plan.observability.event_trace import EventTrace
from travel_plan.web.server import _stream_event
from travel_plan.web.workflow_visualization import workflow_graph, workflow_node_id


def _states(graph):
    return {node["id"]: node["status"] for node in graph["nodes"]}


def _edge(graph, source, target):
    return next(edge for edge in graph["edges"]
                if edge["from"] == source and edge["to"] == target)


def test_events_map_to_runtime_graph_nodes():
    graph = workflow_graph([
        {"event_type": "STAGE_STARTED", "stage": "REQUIREMENT", "status": "RUNNING"},
        {"event_type": "AGENT_COMPLETED", "stage": "REQUIREMENT", "status": "COMPLETED"},
        {"event_type": "STAGE_STARTED", "stage": "PLANNER", "status": "RUNNING"},
    ])
    states = _states(graph)
    assert states["requirement"] == "completed"
    assert states["planner"] == states["route"] == "running"
    assert states["meal"] == states["hotel"] == "running"


def test_unexecuted_nodes_are_pending_and_running_node_is_highlightable():
    states = _states(workflow_graph([
        {"event_type": "STAGE_STARTED", "stage": "RETRIEVAL", "status": "RUNNING"},
    ]))
    assert states["retrieval"] == "running"
    assert states["validator"] == "pending"
    assert states["review"] == "pending"


def test_validator_failure_exposes_replan_loop_without_reasoning():
    graph = workflow_graph([
        {"event_type": "VALIDATOR_BLOCKED", "stage": "VALIDATOR", "status": "WARNING"},
    ])
    states = _states(graph)
    assert states["validator"] == "failed"
    assert states["repair"] == "running"
    assert {("validator", "repair"), ("repair", "validator")} <= {
        (edge["from"], edge["to"]) for edge in graph["edges"]
    }
    assert "思考过程" in graph["notice"]
    assert "prompt" not in str(graph).lower()


def test_nodes_have_user_labels_descriptions_and_preserve_technical_names():
    nodes = {node["id"]: node for node in workflow_graph([])["nodes"]}
    assert nodes["requirement"]["display_name"] == "理解旅行需求"
    assert nodes["route"]["display_name"] == "优化每日路线"
    assert nodes["route"]["technical_label"] == "Route Planner"
    assert "距离" in nodes["route"]["description"]
    assert nodes["output"]["display_name"] == "生成旅行方案"


def test_duration_is_copied_only_from_trace_event():
    graph = workflow_graph([
        {"event_type": "STAGE_STARTED", "stage": "VALIDATOR", "status": "RUNNING"},
        {"event_type": "STAGE_COMPLETED", "stage": "VALIDATOR", "status": "COMPLETED", "duration_ms": 15320},
    ])
    nodes = {node["id"]: node for node in graph["nodes"]}
    assert nodes["validator"]["duration_ms"] == 15320
    assert "duration_ms" not in nodes["review"]


def test_workflow_elapsed_preserves_sub_millisecond_precision(monkeypatch):
    monkeypatch.setattr(workflow_module, "monotonic", lambda: 10.00037)

    duration_ms = workflow_module.TravelWorkflow._elapsed(10.0)

    assert duration_ms == pytest.approx(0.37)
    assert isinstance(duration_ms, float)


def test_float_duration_survives_trace_stream_and_graph_contract(tmp_path):
    trace = EventTrace(tmp_path)
    trace.record(
        "precision-trip", 1, None, "STAGE_COMPLETED", "validator",
        {"stage": "VALIDATOR", "duration_ms": 0.37},
    )
    recorded = json.loads(
        (tmp_path / "precision-trip" / "events.jsonl").read_text(encoding="utf-8")
    )

    streamed = _stream_event(recorded)
    graph = workflow_graph([streamed])
    validator = next(node for node in graph["nodes"] if node["id"] == "validator")

    assert recorded["details"]["duration_ms"] == 0.37
    assert streamed["duration_ms"] == 0.37
    assert validator["duration_ms"] == 0.37
    assert graph["summary"]["recorded_duration_ms"] == 0.37


def test_graph_exposes_deterministic_architecture_layout_and_trace_summary():
    graph = workflow_graph([
        {"event_type": "STAGE_COMPLETED", "stage": "RETRIEVAL", "status": "COMPLETED", "duration_ms": 1200},
        {"event_type": "STAGE_STARTED", "stage": "VALIDATOR", "status": "RUNNING"},
    ])
    nodes = {node["id"]: node for node in graph["nodes"]}
    assert nodes["retrieval"]["layout"] == {"column": 2, "row": 3}
    assert nodes["repair"]["layout"]["column"] == 4
    assert nodes["requirement_refinement"]["layout"]["column"] == 7
    assert graph["summary"]["active_node_id"] == "validator"
    assert graph["summary"]["recorded_duration_ms"] == 1200
    assert graph["summary"]["counts"]["running"] == 1
    assert [phase["label"] for phase in graph["phases"]] == [
        "主流程", "反馈优化闭环"
    ]


def test_event_mapping_is_explicit_and_unknown_events_are_not_guessed():
    assert workflow_node_id({"event_type": "PLAN_GENERATED", "stage": "ROUTE_PLAN"}) == "route"
    assert workflow_node_id({"event_type": "STAGE_STARTED", "stage": "REVIEW"}) == "review"
    assert workflow_node_id({"event_type": "UNRECOGNIZED", "stage": "REVIEW"}) is None


def test_empty_graph_is_waiting_and_has_no_fake_execution_state():
    graph = workflow_graph([])
    assert graph["summary"]["startup_status"] == "WAITING_START"
    assert graph["summary"]["counts"]["running"] == 0
    assert graph["summary"]["counts"]["completed"] == 0
    assert all("duration_ms" not in node for node in graph["nodes"])


def test_workflow_started_replaces_waiting_state_from_real_event():
    graph = workflow_graph([{"event_type": "WORKFLOW_STARTED", "status": "RUNNING"}])
    assert graph["summary"]["startup_status"] == "STARTED"
    assert _states(graph)["input"] == "completed"


def test_graph_contains_complete_feedback_loop_architecture():
    graph = workflow_graph([])
    nodes = {node["id"]: node for node in graph["nodes"]}

    assert nodes["review"]["technical_label"] == "Review Agent"
    assert nodes["requirement_refinement"]["technical_label"] == "Requirement Refinement"
    assert nodes["scoped_replanner"]["technical_label"] == "Scoped Replanner"
    assert nodes["feedback_validator"]["technical_label"] == "Hard Validator"
    assert nodes["feedback_validator"]["display_name"] == "再次验证"
    assert all(nodes[node_id]["description"] for node_id in (
        "review", "requirement_refinement", "scoped_replanner", "feedback_validator"
    ))
    assert {
        ("review", "requirement_refinement"),
        ("requirement_refinement", "scoped_replanner"),
        ("scoped_replanner", "feedback_validator"),
        ("feedback_validator", "output"),
    } <= {(edge["from"], edge["to"]) for edge in graph["edges"]
          if edge["edge_type"] == "feedback"}


def test_review_pass_keeps_feedback_capability_available():
    graph = workflow_graph([
        {"event_type": "REVIEW_COMPLETED", "stage": "REVIEW", "passed": True},
    ])

    assert all(edge["execution_status"] == "available"
               for edge in graph["edges"] if edge["edge_type"] == "feedback")


def test_review_failure_executes_only_event_evidenced_feedback_path():
    graph = workflow_graph([
        {"event_type": "REVIEW_COMPLETED", "stage": "REVIEW", "passed": False},
    ])

    assert _edge(graph, "review", "requirement_refinement")["execution_status"] == "executed"
    assert _edge(graph, "requirement_refinement", "scoped_replanner")["execution_status"] == "available"
    assert _edge(graph, "scoped_replanner", "feedback_validator")["execution_status"] == "available"


def test_explicit_started_event_marks_current_feedback_edge_active():
    graph = workflow_graph([
        {"event_type": "REVIEW_FAILED", "stage": "REVIEW"},
        {"event_type": "REQUIREMENT_REFINEMENT_STARTED", "status": "RUNNING"},
    ])

    assert _edge(graph, "review", "requirement_refinement")["execution_status"] == "active"


def test_feedback_execution_advances_only_with_explicit_trace_events():
    graph = workflow_graph([
        {"event_type": "REVIEW_FAILED", "stage": "REVIEW"},
        {"event_type": "AGENT_COMPLETED", "task": "refine_intent_from_review"},
        {"event_type": "REPLAN_COMPLETED", "scope": "DAY"},
    ])

    feedback = [edge for edge in graph["edges"] if edge["edge_type"] == "feedback"]
    assert all(edge["execution_status"] == "executed" for edge in feedback[:3])
    assert feedback[-1]["execution_status"] == "available"


def test_no_events_never_create_a_fake_executed_edge():
    graph = workflow_graph([])

    assert all(edge["execution_status"] == "available" for edge in graph["edges"])


def test_feedback_edges_use_short_hidden_labels_with_tooltips_and_position_dto():
    graph = workflow_graph([])
    feedback = [edge for edge in graph["edges"] if edge["edge_type"] == "feedback"]

    assert [edge["label"] for edge in feedback] == ["反馈", "修正", "验证", "通过"]
    assert all(edge["show_label"] is False for edge in feedback)
    assert all(edge["tooltip"] for edge in feedback)
    assert all(edge["edge_label_position"] == {"position": "middle", "offset": 10}
               for edge in feedback)
    assert "审核反馈优化闭环" not in [edge["label"] for edge in feedback]


def test_feedback_validator_state_follows_only_post_replan_validation_events():
    graph = workflow_graph([
        {"event_type": "REPLAN_COMPLETED", "scope": "DAY"},
        {"event_type": "VALIDATOR_PASSED", "stage": "VALIDATOR",
         "status": "COMPLETED", "duration_ms": 42},
    ])
    node = next(node for node in graph["nodes"] if node["id"] == "feedback_validator")

    assert node["status"] == "completed"
    assert node["event_type"] == "VALIDATOR_PASSED"
    assert node["duration_ms"] == 42
