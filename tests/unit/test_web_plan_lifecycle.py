import json
import threading
from dataclasses import dataclass
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from travel_plan.observability.event_trace import EventTrace
from travel_plan.web.repository import PlanRepository
from travel_plan.web.server import create_server


@dataclass
class FakeState:
    trip_id: str
    version: int
    requirements: dict
    locked_items: list
    rejected_items: list
    rejected_categories: list
    current_plan: dict


class FakeWorkflow:
    versions = {}

    def __init__(self, state_dir):
        self.events = EventTrace(state_dir)

    def execute(self, text, trip_id):
        version = self.versions.get(trip_id, 0) + 1
        self.versions[trip_id] = version
        plan = sample_plan(trip_id, text)
        self.events.record(trip_id, version, version - 1 or None, "AGENT_COMPLETED", "requirement-agent", {"scope": "DAY"})
        self.events.record(trip_id, version, version - 1 or None, "PLAN_GENERATED", "planner", {"scope": "DAY"})
        self.events.record(trip_id, version, version - 1 or None, "VALIDATOR_PASSED", "validator", {"stage": "FINAL_GATE", "issues": []})
        self.events.record(trip_id, version, version - 1 or None, "REVIEW_COMPLETED", "review-agent", {"passed": True, "issues": []})
        state = FakeState(trip_id, version, {"text": text}, [], [], [], plan)
        return plan, state, ""


def sample_plan(trip_id, theme="建筑"):
    return {
        "trip_id": trip_id,
        "days": [{"day": 1, "date": "2026-09-01", "theme": theme, "route_score": 10,
                  "nodes": [{"type": "attraction", "name": "外滩", "start_time": "09:00",
                             "end_time": "10:00", "duration_min": 0, "metadata": {}}]}],
        "hotels": [], "budget": {"tickets": 0, "meals": 0, "hotels": 0, "transport": 0, "total": 0},
        "hotel_decision": {}, "remaining_issues": [], "review_count": 1,
    }


def request_json(base, path, method="GET", payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(base + path, data=body, method=method, headers={"Content-Type": "application/json"})
    with urlopen(request) as response:
        return response.status, json.load(response)


def test_plan_api_lifecycle_preserves_versions_and_exposes_workflow_outputs(tmp_path):
    FakeWorkflow.versions = {}
    repository = PlanRepository()
    factory = lambda root: FakeWorkflow(tmp_path)
    server = create_server(port=0, root=tmp_path, workflow_factory=factory, repository=repository)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        status, created = request_json(base, "/api/plans", "POST", {"request": "上海一天"})
        assert status == 201
        assert created["plan_id"].startswith("plan_") and created["version"] == 1
        plan_id = created["plan_id"]
        original = json.dumps(created["plan"], sort_keys=True, ensure_ascii=False)

        status, modified = request_json(base, f"/api/plans/{plan_id}/modify", "POST", {
            "scope": "DAY", "target": "day1", "instruction": "修改第一天安排",
        })
        assert status == 200 and modified["version"] == 2

        _, versions = request_json(base, f"/api/plans/{plan_id}/versions")
        assert [item["version"] for item in versions] == [1, 2]
        assert json.dumps(versions[0]["plan"], sort_keys=True, ensure_ascii=False) == original

        _, events = request_json(base, f"/api/plans/{plan_id}/events")
        assert [event["stage"] for event in events] == ["REQUIREMENT", "ROUTE_PLAN", "VALIDATE", "REVIEW"]
        _, review = request_json(base, f"/api/plans/{plan_id}/review")
        assert review == {"passed": True, "checks": [], "summary": "方案整体合理"}
        assert repository.current(plan_id).state["requirements"] == {"text": "修改第一天安排"}
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_modify_rejects_unknown_scope(tmp_path):
    FakeWorkflow.versions = {}
    server = create_server(port=0, root=tmp_path, workflow_factory=lambda root: FakeWorkflow(tmp_path))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        _, created = request_json(base, "/api/plans", "POST", {"request": "上海一天"})
        try:
            request_json(base, f"/api/plans/{created['plan_id']}/modify", "POST", {
                "scope": "CITY", "instruction": "修改",
            })
            raise AssertionError("invalid scope was accepted")
        except HTTPError as exc:
            assert exc.code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
