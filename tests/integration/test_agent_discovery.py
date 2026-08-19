import shutil,subprocess
import pytest

@pytest.mark.skipif(not shutil.which("opencode"),reason="OpenCode executable is not installed")
def test_project_agents_are_discoverable():
    output=subprocess.run(["opencode","agent","list"],text=True,capture_output=True,check=True).stdout
    assert "requirement-agent" in output and "review-agent" in output
