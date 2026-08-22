from pathlib import Path

from travel_plan.web.server import _stream_event

STATIC = Path(__file__).parents[2] / "src" / "travel_plan" / "web" / "static"


def test_stream_dto_links_real_event_to_workflow_node():
    event = _stream_event({"sequence": 7, "event_type": "PLAN_GENERATED", "actor": "planner", "timestamp": "2026-08-22T15:01:15Z", "details": {"duration_ms": 15300}})
    assert event["workflow_node_id"] == "route"


def test_unknown_stream_event_has_no_workflow_link():
    event = _stream_event({"sequence": 8, "event_type": "UNKNOWN_EVENT", "actor": "other", "timestamp": "", "details": {}})
    assert event["workflow_node_id"] is None


def test_renderer_supports_bidirectional_click_location_and_waiting_state():
    javascript = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "selectWorkflowNode(event.workflow_node_id,'timeline')" in javascript
    assert "selectWorkflowNode(node.dataset.node,'graph')" in javascript
    assert "node.open=true" in javascript
    assert "startup_status==='WAITING_START'" in javascript
    relevant = javascript[javascript.index("function renderWorkflowGraph"):javascript.index("function renderAgentRuntime")]
    assert "setTimeout" not in relevant
