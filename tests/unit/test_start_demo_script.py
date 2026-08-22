from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "start_demo.bat"


def test_windows_demo_launcher_exists_and_has_reliability_checks():
    assert SCRIPT.is_file()
    content = SCRIPT.read_text(encoding="utf-8").lower()

    assert "%~dp0" in content
    assert "cd /d" in content
    assert "python --version" in content
    assert "sys.version_info >= (3, 11)" in content
    assert "set \"pythonpath=" in content
    assert "src\\travel_plan\\web\\server.py" in content
    assert "data\\demo\\shanghai_family_trip.json" in content
    assert "import fastapi, uvicorn" in content
    assert "port 8000 is already in use" in content
    assert "logs\\start_demo.log" in content
    assert "python -m travel_plan.web.server" in content
    assert "pause" in content
    assert "where opencode" in content
    assert "--agent-mode" in content
    assert "deterministic offline agent" in content
    assert 'set "agent_mode=deterministic"' in content


def test_posix_launcher_detects_runtime_and_supports_forcing_mode():
    content = (ROOT / "scripts" / "start_demo.sh").read_text(encoding="utf-8").lower()
    assert "command -v opencode" in content
    assert "--agent-mode" in content
    assert "[4/6] agent runtime" in content
    assert "deterministic offline agent" in content
    assert "agent_mode=deterministic" in content


def test_launchers_print_demo_url_and_keep_browser_failure_non_fatal():
    for name in ("start_demo.bat", "start_demo.sh"):
        content = (ROOT / "scripts" / name).read_text(encoding="utf-8").lower()
        assert "http://localhost:8000" in content
        assert "browser auto open failed" in content
    assert "start """ in (ROOT / "scripts/start_demo.bat").read_text(encoding="utf-8").lower()
    posix = (ROOT / "scripts/start_demo.sh").read_text(encoding="utf-8").lower()
    assert "xdg-open" in posix and "open http://localhost:8000" in posix
    assert ") &" in posix
