import json
import threading
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from travel_plan.web.repository import PlanRepository
from travel_plan.web.server import create_server


ROOT = Path(__file__).resolve().parents[2]


def _request(server, path, method="GET"):
    request = Request(f"http://127.0.0.1:{server.server_port}{path}", method=method)
    with urlopen(request, timeout=60) as response:
        return response.status, json.load(response)


def test_demo_data_can_be_loaded():
    scenario = json.loads((ROOT / "data/demo/shanghai_family_trip.json").read_text(encoding="utf-8"))
    assert scenario["id"] == "shanghai_family_trip"
    assert "迪士尼" in scenario["request"]
    assert "4天" in scenario["request"]


def test_demo_api_uses_workflow_and_returns_explainable_itinerary(tmp_path):
    calls = []

    @dataclass
    class FakeState:
        version: int = 1

    class FakeEvents:
        root = tmp_path / "state"

    class FakeWorkflow:
        events = FakeEvents()

        def execute(self, text, plan_id):
            calls.append((text, plan_id))
            plan = {
                "days": [{"day": 1, "date": "2026-08-21", "theme": "亲子体验", "route_score": 1.0, "nodes": []}],
                "hotels": [], "budget": {"tickets": 0, "meals": 0, "hotels": 0, "transport": 0, "total": 0},
                "hotel_decision": {"action": "KEEP", "reason": "减少换酒店"},
            }
            return plan, FakeState(), None

    def workflow_factory(root):
        assert root == ROOT
        return FakeWorkflow()

    server = create_server(port=0, root=ROOT, workflow_factory=workflow_factory, repository=PlanRepository())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, scenarios = _request(server, "/api/demo")
        assert status == 200
        assert scenarios == [{"id": "shanghai_family_trip", "name": "上海亲子四日游", "description": "科技 + 自然 + 夜景，公共交通少步行"}]

        status, result = _request(server, "/api/demo/shanghai_family_trip/run", "POST")
        assert status == 201
        assert result["plan_id"].startswith("demo_shanghai_family_trip_")
        assert result["version"] == 1
        assert result["itinerary"] == result["plan"]["days"]
        assert calls and "迪士尼" in calls[0][0]

        _, explanation = _request(server, f"/api/plans/{result['plan_id']}/explainability")
        assert explanation["days"][0]["title"] == "第 1 天 · 亲子体验"
    finally:
        server.shutdown()
        server.server_close()
