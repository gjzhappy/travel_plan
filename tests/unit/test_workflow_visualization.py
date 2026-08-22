from travel_plan.web.workflow_visualization import workflow_graph


def _states(graph):
    return {node["id"]: node["status"] for node in graph["nodes"]}


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


def test_graph_exposes_deterministic_architecture_layout_and_trace_summary():
    graph = workflow_graph([
        {"event_type": "STAGE_COMPLETED", "stage": "RETRIEVAL", "status": "COMPLETED", "duration_ms": 1200},
        {"event_type": "STAGE_STARTED", "stage": "VALIDATOR", "status": "RUNNING"},
    ])
    nodes = {node["id"]: node for node in graph["nodes"]}
    assert nodes["retrieval"]["layout"] == {"column": 3, "row": 1}
    assert nodes["repair"]["layout"]["row"] == 4
    assert graph["summary"]["active_node_id"] == "validator"
    assert graph["summary"]["recorded_duration_ms"] == 1200
    assert graph["summary"]["counts"]["running"] == 1
    assert [phase["label"] for phase in graph["phases"]] == [
        "需求理解", "信息准备", "行程编排", "质量校验", "方案交付"
    ]
