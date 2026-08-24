import importlib.util
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
BAT = ROOT / "scripts" / "start_demo.bat"
PYTHON = ROOT / "scripts" / "start_demo.py"


def load_launcher():
    spec = importlib.util.spec_from_file_location("start_demo", PYTHON)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_bat_is_ascii_crlf_minimal_wrapper():
    raw = BAT.read_bytes()
    assert raw.isascii()
    assert not raw.startswith((b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff"))
    assert b"\n" in raw and raw.count(b"\r\n") == raw.count(b"\n")
    content = raw.decode("ascii").lower()
    forbidden = (
        "cmd /c", "powershell", "pythonpath", "project_root", "agent_mode=",
        "webbrowser", "xdg-open", 'start "" "http', "|",
    )
    assert all(item not in content for item in forbidden)
    assert not any(line.rstrip().endswith("^") for line in content.splitlines())
    assert content.count("(") == 0


def test_bat_bootstrap_contract():
    content = BAT.read_text(encoding="ascii").lower()
    for expected in ("%~dp0", "start_demo.py", "where py", "where python", "%*"):
        assert expected in content


def test_project_root_is_independent_of_working_directory(tmp_path):
    command = (
        "import importlib.util; "
        f"s=importlib.util.spec_from_file_location('launcher', {str(PYTHON)!r}); "
        "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(m.project_root())"
    )
    result = subprocess.run([sys.executable, "-c", command], cwd=tmp_path, text=True, capture_output=True, check=True)
    assert Path(result.stdout.strip()) == ROOT


def test_agent_mode_defaults_and_explicit_opencode():
    launcher = load_launcher()
    assert launcher.parse_args([]).agent_mode == "deterministic"
    assert launcher.parse_args(["--agent-mode", "opencode"]).agent_mode == "opencode"
    assert launcher.parse_args(["--agent-mode", "auto"]).agent_mode == "auto"


def test_validation_failure_reports_absolute_log_path(monkeypatch, tmp_path, capsys):
    launcher = load_launcher()
    monkeypatch.setattr(launcher, "project_root", lambda: tmp_path)
    result = launcher.launch(launcher.parse_args([]))
    error = capsys.readouterr().err
    assert result != 0
    assert f"Log saved: {(tmp_path / 'logs' / 'start_demo.log').resolve()}" in error


def test_browser_failure_is_nonfatal(monkeypatch, capsys):
    launcher = load_launcher()
    monkeypatch.setattr(launcher.webbrowser, "open", lambda _url: False)
    assert launcher.open_browser() is False
    output = capsys.readouterr().out
    assert "Browser could not be opened automatically." in output
    assert launcher.DEMO_URL in output


def test_posix_launcher_delegates_to_python_launcher():
    content = (ROOT / "scripts" / "start_demo.sh").read_text(encoding="ascii")
    assert "start_demo.py" in content
    assert '"$@"' in content
    assert "agent-mode" not in content
