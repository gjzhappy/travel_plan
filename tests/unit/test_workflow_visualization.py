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
