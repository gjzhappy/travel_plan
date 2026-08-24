#!/usr/bin/env python3
"""Cross-platform launcher for the existing Travel Plan web demo."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser


DEMO_URL = "http://localhost:8000"
MINIMUM_PYTHON = (3, 11)
EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
READINESS_TIMEOUT_SECONDS = 15.0


def project_root() -> Path:
    """Resolve the repository independently of the caller's working directory."""
    return Path(__file__).resolve().parent.parent


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the Travel Plan web demo")
    parser.add_argument(
        "--agent-mode",
        choices=("deterministic", "opencode", "auto"),
        default="deterministic",
    )
    return parser.parse_args(argv)


def _stage(number: int, title: str, action: str) -> None:
    print(f"\n[{number}/6] {title}")
    print(f"      {action}", flush=True)


def open_browser(url: str = DEMO_URL) -> bool:
    """Try to open the demo without making browser availability fatal."""
    try:
        opened = webbrowser.open(url)
    except Exception:
        opened = False
    if not opened:
        print("      Browser could not be opened automatically.", flush=True)
        print(f"      Please visit: {url}", flush=True)
    return bool(opened)


def _environment(root: Path) -> dict[str, str]:
    environment = os.environ.copy()
    source = str(root / "src")
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = source + (os.pathsep + existing if existing else "")
    return environment


def _runtime_label(mode: str) -> str:
    if mode == "opencode" or (mode == "auto" and shutil.which("opencode")):
        return "OpenCode Agent"
    return "Deterministic Offline Agent"


def _validate_environment(root: Path, mode: str) -> str | None:
    if sys.version_info < MINIMUM_PYTHON:
        return "Python 3.11+ is required."
    required = (
        root / "src" / "travel_plan" / "web" / "server.py",
        root / "data" / "demo" / "shanghai_family_trip.json",
        root / "scripts" / "init_db.py",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        return "Required project file is missing: " + missing[0]
    if mode == "opencode" and not shutil.which("opencode"):
        return "--agent-mode opencode requires the opencode command."
    return None


def _poi_count(database: Path) -> int | None:
    """Read one metadata value; never construct retrieval or embedding services."""
    if not database.is_file():
        return None
    try:
        with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection:
            return int(connection.execute("SELECT COUNT(*) FROM pois").fetchone()[0])
    except sqlite3.Error:
        return None


def _wait_until_ready(process: subprocess.Popen, timeout: float = READINESS_TIMEOUT_SECONDS) -> bool:
    """Poll localhost until it responds, the server exits, or the deadline passes."""
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if process.poll() is not None:
            return False
        try:
            with urlopen(DEMO_URL, timeout=0.25) as response:
                if response.status < 500:
                    return True
        except (OSError, URLError):
            pass
        time.sleep(0.05)
    return False


def launch(args: argparse.Namespace) -> int:
    entered_at = time.perf_counter()
    print("========================================")
    print(" Shanghai AI Travel Planner Demo")
    print("========================================", flush=True)

    _stage(1, "Python Environment", "Checking...")
    root_started = time.perf_counter()
    root = project_root()
    log_path = (root / "logs" / "start_demo.log").resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    environment = _environment(root)

    check_started = time.perf_counter()
    error = _validate_environment(root, args.agent_mode)
    if error:
        log_path.write_text(f"[ERROR] {error}\n", encoding="utf-8")
        print(f"[ERROR] {error}", file=sys.stderr, flush=True)
        print(f"Log saved: {log_path}", file=sys.stderr, flush=True)
        return 1
    print(f"      OK - Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}", flush=True)

    database = root / "data" / "travel.db"
    _stage(2, "Shanghai Knowledge Base", "Checking...")
    knowledge_started = time.perf_counter()
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"[TIMING] Python process entered: {entered_at:.6f}\n")
        log.write(f"[TIMING] Argument parsing: {getattr(args, '_parse_seconds', 0.0):.3f}s\n")
        log.write(f"[TIMING] Project root/setup: {check_started - root_started:.3f}s\n")
        log.write(f"[TIMING] Root/environment validation: {time.perf_counter() - check_started:.3f}s\n")
        if not database.is_file():
            print("      Initializing required local database...", flush=True)
            result = subprocess.run(
                [sys.executable, str(root / "scripts" / "init_db.py")],
                cwd=root, env=environment, stdout=log, stderr=subprocess.STDOUT, check=False,
            )
            if result.returncode:
                print("[ERROR] Demo database initialization failed.", file=sys.stderr, flush=True)
                print(f"Log saved: {log_path}", file=sys.stderr, flush=True)
                return result.returncode
        count = _poi_count(database)
        if count is None:
            print("[ERROR] Demo database is unavailable.", file=sys.stderr, flush=True)
            return 1
        print(f"      OK - {count} POIs", flush=True)
        log.write(f"[TIMING] Knowledge-base readiness: {time.perf_counter() - knowledge_started:.3f}s\n")

        _stage(3, "Embedding Configuration", "Checking configuration...")
        embedding_started = time.perf_counter()
        # This is deliberately a configuration check. The application owns model loading.
        print(f"      OK - {EMBEDDING_MODEL} (loads when needed)", flush=True)
        log.write(f"[TIMING] Embedding configuration: {time.perf_counter() - embedding_started:.3f}s\n")

        _stage(4, "Agent Runtime", "Checking configuration...")
        print(f"      OK - {_runtime_label(args.agent_mode)}", flush=True)

        _stage(5, "Web Server", "Loading application...")
        command = [
            sys.executable, "-m", "travel_plan.web.server", "--host", "127.0.0.1",
            "--port", "8000", "--agent-mode", args.agent_mode,
        ]
        server_started = time.perf_counter()
        log.write("[INFO] Starting existing travel_plan.web.server\n")
        log.flush()
        process = subprocess.Popen(
            command, cwd=root, env=environment, stdout=log, stderr=subprocess.STDOUT,
        )
        print("      Starting server...", flush=True)
        if not _wait_until_ready(process):
            if process.poll() is None:
                process.terminate()
                process.wait()
            print("[ERROR] Web server did not become ready.", file=sys.stderr, flush=True)
            print(f"Log saved: {log_path}", file=sys.stderr, flush=True)
            return process.returncode or 1
        log.write(f"[TIMING] Server import/start/readiness: {time.perf_counter() - server_started:.3f}s\n")
        print("      OK - Server is ready", flush=True)

        _stage(6, "Browser", f"Opening {DEMO_URL}")
        browser_started = time.perf_counter()
        open_browser()
        print(f"\nDemo URL:\n{DEMO_URL}", flush=True)
        log.write(f"[TIMING] Browser request: {time.perf_counter() - browser_started:.3f}s\n")
        log.write(f"[TIMING] Launcher to ready: {time.perf_counter() - entered_at:.3f}s\n")
        log.flush()
        return_code = process.wait()

    if return_code:
        print("[ERROR] Web server exited with an error.", file=sys.stderr, flush=True)
        print(f"Log saved: {log_path}", file=sys.stderr, flush=True)
    return return_code


def main(argv: list[str] | None = None) -> int:
    parse_started = time.perf_counter()
    args = parse_args(argv)
    args._parse_seconds = time.perf_counter() - parse_started
    return launch(args)


if __name__ == "__main__":
    raise SystemExit(main())
