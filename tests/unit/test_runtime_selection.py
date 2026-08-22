from dataclasses import replace

import pytest

from travel_plan.agents.client import DeterministicAgentClient, OpenCodeAgentClient
from travel_plan.config import DEFAULT_CONFIG
from travel_plan.providers import ProviderFactory
from travel_plan.retrieval.map_client import MockMapClient
from travel_plan.retrieval.weather_client import MockWeatherClient


def test_default_stays_deterministic_when_opencode_command_exists():
    providers = ProviderFactory.create(DEFAULT_CONFIG, lambda _: "/bin/opencode")
    assert isinstance(providers.agent, DeterministicAgentClient)
    assert providers.agent_runtime == "deterministic"


def test_explicit_auto_can_select_opencode_when_command_exists():
    config = replace(DEFAULT_CONFIG, agent_runtime_mode="auto")
    providers = ProviderFactory.create(config, lambda _: "/bin/opencode")
    assert isinstance(providers.agent, OpenCodeAgentClient)
    assert providers.agent_runtime == "opencode"


def test_auto_falls_back_to_deterministic_without_command():
    providers = ProviderFactory.create(DEFAULT_CONFIG, lambda _: None)
    assert isinstance(providers.agent, DeterministicAgentClient)
    assert providers.agent_runtime == "deterministic"


def test_forced_opencode_fails_clearly_when_missing():
    config = replace(DEFAULT_CONFIG, agent_runtime_mode="opencode")
    with pytest.raises(RuntimeError, match="opencode command was not found"):
        ProviderFactory.create(config, lambda _: None)


def test_external_providers_remain_mock_in_opencode_mode():
    config = replace(DEFAULT_CONFIG, agent_runtime_mode="opencode")
    providers = ProviderFactory.create(config, lambda _: "/bin/opencode")
    assert isinstance(providers.map, MockMapClient)
    assert isinstance(providers.weather, MockWeatherClient)
