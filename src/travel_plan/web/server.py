import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import unquote, urlparse

from travel_plan.main import build_workflow
from travel_plan.web.presenter import present_plan

STATIC_DIR = Path(__file__).with_name("static")


class TravelRequestHandler(BaseHTTPRequestHandler):
    workflow_factory: Callable = staticmethod(build_workflow)
    root = Path(".")

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
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
        if urlparse(self.path).path != "/api/plans":
            self._json(HTTPStatus.NOT_FOUND, {"error": "接口不存在"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 20_000:
                raise ValueError("请求内容不能为空")
            payload = json.loads(self.rfile.read(length))
            request = str(payload.get("request", "")).strip()
            if not request:
                raise ValueError("请先描述你的旅行需求")
            workflow = self.workflow_factory(root=self.root)
            plan, state, _ = workflow.execute(request, payload.get("trip_id"))
            self._json(HTTPStatus.CREATED, present_plan(plan, state.version))
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            self.log_error("planning failed: %s", exc)
            self._json(HTTPStatus.UNPROCESSABLE_ENTITY, {"error": f"暂时无法生成可行方案：{exc}"})

    def _json(self, status: HTTPStatus, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server(host="127.0.0.1", port=8000, root=Path("."), workflow_factory=build_workflow):
    handler = type("ConfiguredTravelHandler", (TravelRequestHandler,), {
        "root": Path(root), "workflow_factory": staticmethod(workflow_factory)
    })
    return ThreadingHTTPServer((host, port), handler)


def cli():
    import argparse
    parser = argparse.ArgumentParser(description="Travel Plan Web Demo")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = create_server(args.host, args.port)
    print(f"Travel Plan Web: http://{args.host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    cli()
