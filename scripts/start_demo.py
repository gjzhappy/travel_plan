#!/usr/bin/env python3
"""Cross-platform launcher for the existing Travel Plan web demo."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import webbrowser


DEMO_URL = "http://localhost:8000"
MINIMUM_PYTHON = (3, 11)


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


def open_browser(url: str = DEMO_URL) -> bool:
    """Try to open the demo without making browser availability fatal."""
    try:
        opened = webbrowser.open(url)
    except Exception:
        opened = False
    if not opened:
        print("Browser could not be opened automatically.")
        print("Please visit:")
        print(url)
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


def _validate(root: Path, mode: str) -> str | None:
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


def _print_startup(mode: str) -> None:
    print("========================================")
    print(" Shanghai AI Travel Planner Demo")
    print("========================================")
    print("\n[1/6] Python Environment")
    print(f"      OK - Python {sys.version_info.major}.{sys.version_info.minor}+")
    print("\n[2/6] Shanghai Knowledge Base")
    print("      OK")
    print("\n[3/6] Embedding Model")
    print("      BAAI/bge-small-zh-v1.5")
    print("\n[4/6] Agent Runtime")
    print(f"      {_runtime_label(mode)}")
    print("\n[5/6] Web Server")
    print("      Starting...")
    print("\n[6/6] Browser")
    print(f"      Opening {DEMO_URL}")


def launch(args: argparse.Namespace) -> int:
    root = project_root()
    log_path = (root / "logs" / "start_demo.log").resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    environment = _environment(root)

    error = _validate(root, args.agent_mode)
    if error:
        log_path.write_text(f"[ERROR] {error}\n", encoding="utf-8")
        print(f"[ERROR] {error}", file=sys.stderr)
        print(f"Log saved: {log_path}", file=sys.stderr)
        return 1

    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"[INFO] Project root: {root}\n")
        log.write(f"[INFO] Agent mode: {args.agent_mode}\n")
        if not (root / "data" / "travel.db").is_file():
            result = subprocess.run(
                [sys.executable, str(root / "scripts" / "init_db.py")],
                cwd=root,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
            if result.returncode:
                print("[ERROR] Demo database initialization failed.", file=sys.stderr)
                print(f"Log saved: {log_path}", file=sys.stderr)
                return result.returncode

        _print_startup(args.agent_mode)
        open_browser()
        command = [
            sys.executable,
            "-m",
            "travel_plan.web.server",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--agent-mode",
            args.agent_mode,
        ]
        log.write("[INFO] Starting existing travel_plan.web.server\n")
        log.flush()
        result = subprocess.run(
            command,
            cwd=root,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )

    if result.returncode:
        print("[ERROR] Web server exited with an error.", file=sys.stderr)
        print(f"Log saved: {log_path}", file=sys.stderr)
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    return launch(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
