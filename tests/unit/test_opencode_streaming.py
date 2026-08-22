import subprocess

import pytest

from travel_plan.agents.client import OpenCodeAgentClient
from travel_plan.errors import AgentOutputValidationError


SCHEMA = {"type": "object", "required": ["ok"], "properties": {"ok": {"type": "boolean"}}}


def test_opencode_subprocess_always_decodes_utf8(monkeypatch):
    observed = {}

    def run(*args, **kwargs):
        observed.update(kwargs)
        return subprocess.CompletedProcess(args[0], 0, '{"ok": true} 中文', None)

    monkeypatch.setattr(subprocess, "run", run)
    assert OpenCodeAgentClient().invoke("requirement-agent", {}, SCHEMA) == {"ok": True}
    assert observed["encoding"] == "utf-8"
    assert observed["errors"] == "replace"
    assert observed["text"] is True


def test_empty_agent_output_has_explicit_stage_and_reason(monkeypatch):
    monkeypatch.setattr(
        subprocess, "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, None, None),
    )
    with pytest.raises(AgentOutputValidationError) as caught:
        OpenCodeAgentClient().invoke("requirement-agent", {}, SCHEMA)
    message = str(caught.value)
    assert "Agent output empty" in message
    assert "stage=requirement-agent" in message
    assert "reason=subprocess output unavailable" in message
