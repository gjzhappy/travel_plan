from dataclasses import replace
import json
from pathlib import Path

from travel_plan.agents.client import DeterministicAgentClient, OpenCodeAgentClient
from travel_plan.config import DEFAULT_CONFIG
from travel_plan.main import build_workflow
from travel_plan.retrieval.map_client import MockMapClient
from travel_plan.retrieval.weather_client import MockWeatherClient


def test_lock_day_continues_through_review_and_final_validator(tmp_path):
    workflow = build_workflow(Path.cwd(), tmp_path)
    original, _, _ = workflow.execute("上海一日游", "lock_contract")
    locked, state, _ = workflow.execute("第一天很满意，锁定不要再改", "lock_contract")

    assert locked["days"] == original["days"]
    assert state.locked_items == ["DAY:1"]
    trace = tmp_path / "lock_contract" / "events.jsonl"
    events = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    version_two = [event for event in events if event["plan_version"] == 2]
    assert any(event["event_type"] == "REVIEW_COMPLETED" for event in version_two)
    assert any(
        event["actor"] == "validator"
        and event["details"]["stage"] == "FINAL_GATE"
        for event in version_two
    )
    assert version_two[-1]["event_type"] == "PLAN_VERSION_SAVED"


def test_mock_mode_only_selects_deterministic_providers(tmp_path):
    workflow = build_workflow(Path.cwd(), tmp_path)
    assert isinstance(workflow.requirements.client, DeterministicAgentClient)
    assert isinstance(workflow.map, MockMapClient)
    assert isinstance(workflow.retrieval.weather, MockWeatherClient)


def test_mock_workflow_is_deterministic_across_runs(tmp_path):
    first = build_workflow(Path.cwd(), tmp_path / "one")
    second = build_workflow(Path.cwd(), tmp_path / "two")
    result_one = first.execute("上海两天科技亲子游", "same_trip")
    result_two = second.execute("上海两天科技亲子游", "same_trip")

    assert result_one[0] == result_two[0]
    assert result_one[1].requirements == result_two[1].requirements
    assert result_one[2] == result_two[2]


def test_legacy_mock_flag_cannot_enable_external_providers(tmp_path):
    workflow = build_workflow(
        Path.cwd(), tmp_path, replace(DEFAULT_CONFIG, mock_mode=False)
    )
    assert isinstance(workflow.map, MockMapClient)
    assert isinstance(workflow.retrieval.weather, MockWeatherClient)
