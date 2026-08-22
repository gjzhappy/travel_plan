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
