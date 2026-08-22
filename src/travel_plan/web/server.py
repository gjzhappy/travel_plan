import json
import mimetypes
import uuid
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import unquote, urlparse

from travel_plan.main import build_workflow
from travel_plan.config import DEFAULT_CONFIG, load_config
from travel_plan.providers import ProviderFactory
from travel_plan.observability.trace_reader import TraceReader
from travel_plan.web.presenter import present_plan
from travel_plan.web.explainability import build_explainability
from travel_plan.web.repository import PlanRepository

STATIC_DIR = Path(__file__).with_name("static")
DEMO_DIR = Path("data/demo")


class TravelRequestHandler(BaseHTTPRequestHandler):
    workflow_factory: Callable = staticmethod(build_workflow)
    root = Path(".")
    repository = PlanRepository()
    system_status = {}

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == "/api/demo":
            self._json(HTTPStatus.OK, self._demo_scenarios())
            return
        if path == "/api/system/status":
            self._json(HTTPStatus.OK, self.system_status)
            return
        if path.startswith("/api/plans/"):
            self._get_plan_resource(path)
            return
        relative = "index.html" if path == "/" else path.lstrip("/")
        target = (STATIC_DIR / relative).resolve()
        if STATIC_DIR.resolve() not in target.parents or not target.is_file():
            self._json(HTTPStatus.NOT_FOUND, {"error": "页面不存在"})
            return
        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = unquote(urlparse(self.path).path)
        parts = path.strip("/").split("/")
        if len(parts) == 4 and parts[:2] == ["api", "demo"] and parts[3] == "run":
            self._run_demo(parts[2])
            return
        if len(parts) == 4 and parts[:2] == ["api", "demo"] and parts[3] == "stream":
            self._stream_demo(parts[2])
            return
        if path == "/api/plans":
            self._create_plan()
            return
        if path == "/api/plans/stream":
            self._stream_create_plan()
            return
        if len(parts) == 4 and parts[:2] == ["api", "plans"] and parts[3] == "modify":
            self._modify_plan(parts[2])
            return
        if len(parts) == 5 and parts[:2] == ["api", "plans"] and parts[3:] == ["modify", "stream"]:
            self._stream_modify_plan(parts[2])
            return
        self._json(HTTPStatus.NOT_FOUND, {"error": "接口不存在"})

    def _demo_scenarios(self):
        """Load checked-in presentation data without making planning decisions."""
        scenarios = []
        for path in sorted((self.root / DEMO_DIR).glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            scenarios.append({key: data[key] for key in ("id", "name", "description")})
        return scenarios

    def _run_demo(self, scenario_id: str):
        try:
            path = self.root / DEMO_DIR / f"{scenario_id}.json"
            if not path.is_file():
                self._json(HTTPStatus.NOT_FOUND, {"error": "演示场景不存在"})
                return
            scenario = json.loads(path.read_text(encoding="utf-8"))
            if scenario.get("id") != scenario_id or not str(scenario.get("request", "")).strip():
                raise ValueError("演示场景数据无效")
            plan_id = f"demo_{scenario_id}_{uuid.uuid4().hex}"
            record = self._run_and_save(plan_id, scenario["request"], {
                "request": scenario["request"], "demo_id": scenario_id,
            })
            response = self._plan_response(record)
            response["itinerary"] = record.display_result["days"]
            self._json(HTTPStatus.CREATED, response)
        except (ValueError, json.JSONDecodeError, KeyError) as exc:
            self._json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(exc)})
        except Exception as exc:
            self.log_error("demo planning failed: %s", exc)
            self._json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": f"暂时无法生成演示方案：{exc}"})

    def _stream_demo(self, scenario_id: str):
        try:
            path = self.root / DEMO_DIR / f"{scenario_id}.json"
            if not path.is_file():
                self._json(HTTPStatus.NOT_FOUND, {"error": "演示场景不存在"})
                return
            scenario = json.loads(path.read_text(encoding="utf-8"))
            request = str(scenario.get("request", "")).strip()
            if scenario.get("id") != scenario_id or not request:
                raise ValueError("演示场景数据无效")
            self._stream_workflow(
                f"demo_{scenario_id}_{uuid.uuid4().hex}", request,
                {"request": request, "demo_id": scenario_id},
            )
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": str(exc)})

    def _create_plan(self):
        try:
            payload = self._payload()
            request = str(payload.get("request", "")).strip()
            if not request:
                raise ValueError("请先描述你的旅行需求")
            plan_id = f"plan_{uuid.uuid4().hex}"
            record = self._run_and_save(plan_id, request, {"request": request})
            self._json(HTTPStatus.CREATED, self._plan_response(record))
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            self.log_error("planning failed: %s", exc)
            self._json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": f"暂时无法生成可行方案：{exc}"})

    def _stream_create_plan(self):
        """Run planning on this request and flush each recorded trace event.

        This is newline-delimited JSON rather than simulated progress.  The
        final line contains the same plan response as ``POST /api/plans``.
        """
        try:
            payload = self._payload()
            request = str(payload.get("request", "")).strip()
            if not request:
                raise ValueError("请先描述你的旅行需求")
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        self._stream_workflow(f"plan_{uuid.uuid4().hex}", request, {"request": request})

    def _stream_modify_plan(self, plan_id: str):
        if not self.repository.current(plan_id):
            self._json(HTTPStatus.NOT_FOUND, {"error": "计划不存在"})
            return
        try:
            payload = self._payload()
            scope = str(payload.get("scope", "")).upper()
            instruction = str(payload.get("instruction", "")).strip()
            if scope not in {"GLOBAL", "DAY", "NODE", "MEAL"} or not instruction:
                raise ValueError("请提供有效的修改范围与指令")
            request = {"scope": scope, "target": payload.get("target"), "instruction": instruction}
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        self._stream_workflow(plan_id, instruction, request)

    def _stream_workflow(self, plan_id, text, request):
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        workflow = self.workflow_factory(root=self.root)

        def publish(event):
            self._stream_line({"type": "trace", "event": _stream_event(asdict(event))})

        workflow.events.subscribe(publish)
        try:
            record = self._execute_and_save(workflow, plan_id, text, request)
            self._stream_line({"type": "result", "result": self._plan_response(record)})
        except Exception as exc:
            self.log_error("streaming planning failed: %s", exc)
            self._stream_line({"type": "error", "error": f"暂时无法生成可行方案：{exc}"})

    def _modify_plan(self, plan_id: str):
        if not self.repository.current(plan_id):
            self._json(HTTPStatus.NOT_FOUND, {"error": "接口不存在"})
            return
        try:
            payload = self._payload()
            scope = str(payload.get("scope", "")).upper()
            if scope not in {"GLOBAL", "DAY", "NODE", "MEAL"}:
                raise ValueError("scope 只允许 GLOBAL、DAY、NODE 或 MEAL")
            instruction = str(payload.get("instruction", "")).strip()
            if not instruction:
                raise ValueError("修改指令不能为空")
            request = {"scope": scope, "target": payload.get("target"), "instruction": instruction}
            record = self._run_and_save(plan_id, instruction, request)
            self._json(HTTPStatus.OK, self._plan_response(record))
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            self.log_error("planning failed: %s", exc)
            self._json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": f"暂时无法生成可行方案：{exc}"})

    def _get_plan_resource(self, path: str):
        parts = path.strip("/").split("/")
        if len(parts) not in {3, 4} or parts[:2] != ["api", "plans"]:
            self._json(HTTPStatus.NOT_FOUND, {"error": "接口不存在"})
            return
        plan_id = parts[2]
        record = self.repository.current(plan_id)
        if not record:
            self._json(HTTPStatus.NOT_FOUND, {"error": "计划不存在"})
            return
        resource = parts[3] if len(parts) == 4 else None
        if resource is None:
            self._json(HTTPStatus.OK, self._plan_response(record))
        elif resource == "versions":
            self._json(HTTPStatus.OK, [self._version_response(item) for item in self.repository.versions(plan_id)])
        elif resource == "events":
            self._json(HTTPStatus.OK, record.events)
        elif resource == "review":
            self._json(HTTPStatus.OK, record.review)
        elif resource == "explainability":
            self._json(HTTPStatus.OK, record.explainability)
        else:
            self._json(HTTPStatus.NOT_FOUND, {"error": "接口不存在"})

    def _run_and_save(self, plan_id: str, text: str, request: dict):
        workflow = self.workflow_factory(root=self.root)
        return self._execute_and_save(workflow, plan_id, text, request)

    def _execute_and_save(self, workflow, plan_id: str, text: str, request: dict):
        plan, state, _ = workflow.execute(text, plan_id)
        display = present_plan(plan, state.version, getattr(state, "requirements", {}))
        raw_events = [asdict(event) for event in TraceReader(workflow.events.root).read(plan_id)]
        events = _present_events(raw_events, state.version)
        review = _review_result(raw_events, state.version)
        explainability = build_explainability(
            plan, raw_events, state.version, getattr(state, "requirements", {})
        )
        return self.repository.save(
            plan_id, state.version, request, asdict(state), display, events, review, explainability
        )

    def _stream_line(self, payload):
        body = (json.dumps(payload, ensure_ascii=False) + "\n").encode()
        self.wfile.write(body)
        self.wfile.flush()

    def _payload(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 20_000:
            raise ValueError("请求内容不能为空")
        payload = json.loads(self.rfile.read(length))
        if not isinstance(payload, dict):
            raise ValueError("请求必须是 JSON 对象")
        return payload

    @staticmethod
    def _plan_response(record):
        return {"plan_id": record.plan_id, "version": record.version, "plan": record.display_result}

    @staticmethod
    def _version_response(record):
        """Return a self-contained, read-only visualization snapshot."""
        return {
            "plan_id": record.plan_id,
            "version": record.version,
            "plan": record.display_result,
            "events": record.events,
            "review": record.review,
            "explainability": record.explainability,
            "change": {
                "scope": record.request.get("scope"),
                "target": record.request.get("target"),
                "instruction": record.request.get("instruction"),
            } if record.version > 1 else None,
        }

    def _json(self, status: HTTPStatus, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server(host="127.0.0.1", port=8000, root=Path("."), workflow_factory=build_workflow, repository=None, config=DEFAULT_CONFIG):
    providers = ProviderFactory.create(config)
    status = {"agent_runtime": providers.agent_runtime, "data_mode": "offline", "providers": {"transport": "mock", "weather": "mock", "reservation": "mock", "crowd": "mock"}}
    configured_workflow_factory = (
        (lambda root: build_workflow(root=root, config=config))
        if workflow_factory is build_workflow else workflow_factory
    )
    handler = type("ConfiguredTravelHandler", (TravelRequestHandler,), {
        "root": Path(root), "workflow_factory": staticmethod(configured_workflow_factory),
        "repository": repository or PlanRepository(),
        "system_status": status,
    })
    return ThreadingHTTPServer((host, port), handler)


EVENT_PRESENTATION = {
    ("AGENT_COMPLETED", "requirement-agent"): ("REQUIREMENT", "解析用户需求"),
    ("PLAN_GENERATED", "planner"): ("ROUTE_PLAN", "生成路线"),
    ("VALIDATOR_PASSED", "validator"): ("VALIDATE", "硬约束检查通过"),
    ("VALIDATOR_BLOCKED", "validator"): ("VALIDATE", "硬约束检查发现问题"),
    ("REVIEW_COMPLETED", "review-agent"): ("REVIEW", "审核行程体验"),
}

STAGE_PRESENTATION = {
    "REQUIREMENT": "正在理解旅行需求",
    "RETRIEVAL": "正在检索地点与旅行资料",
    "PLANNER": "正在编排路线、餐饮与住宿",
    "VALIDATOR": "正在检查硬约束与可行性",
    "REVIEW": "正在审核旅行体验",
}


def _stream_event(event):
    """Expose operational facts only; never expose prompts or model reasoning."""
    details = event.get("details", {})
    stage = details.get("stage")
    if not stage:
        label = EVENT_PRESENTATION.get((event["event_type"], event["actor"]))
        stage = label[0] if label else None
    status = "RUNNING" if event["event_type"] in {"WORKFLOW_STARTED", "STAGE_STARTED"} else "COMPLETED"
    if event["event_type"] == "VALIDATOR_BLOCKED":
        status = "WARNING"
    message = STAGE_PRESENTATION.get(stage)
    if event["event_type"] != "STAGE_STARTED":
        label = EVENT_PRESENTATION.get((event["event_type"], event["actor"]))
        message = label[1] if label else message
    return {
        "event_id": event["sequence"], "stage": stage or "WORKFLOW", "status": status,
        "actor": event["actor"], "message": message or "工作流正在执行",
        "timestamp": event.get("timestamp", ""), "duration_ms": details.get("duration_ms"),
    }


def _present_events(events, version):
    """Label recorded events for display without creating workflow events."""
    result = []
    for event in events:
        if event["plan_version"] != version:
            continue
        label = EVENT_PRESENTATION.get((event["event_type"], event["actor"]))
        if label:
            result.append({"stage": label[0], "time": "", "message": label[1], "event_id": event["event_id"]})
    return result


def _review_result(events, version):
    reviews = [event for event in events if event["plan_version"] == version and event["event_type"] == "REVIEW_COMPLETED"]
    if not reviews:
        return {"passed": False, "checks": [], "summary": "暂无审核结果"}
    payload = reviews[-1]["payload"]
    passed = bool(payload.get("passed"))
    checks = [
        {"type": issue.get("type", "EXPERIENCE").upper(), "status": "WARN", "message": issue.get("message", "")}
        for issue in payload.get("issues", [])
    ]
    return {"passed": passed, "checks": checks, "summary": "方案整体合理" if passed else "方案已通过硬约束校验，仍有体验建议"}


def cli():
    import argparse
    parser = argparse.ArgumentParser(description="Travel Plan Web Demo")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--agent-mode", choices=("auto", "opencode", "deterministic"), default="auto")
    args = parser.parse_args()
    config = load_config(agent_runtime_mode=args.agent_mode)
    server = create_server(args.host, args.port, config=config)
    print(f"Travel Plan Web: http://{args.host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    cli()
