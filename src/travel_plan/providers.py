"""Runtime selection at the provider boundary; planning stays mode-agnostic."""
import shutil
from dataclasses import dataclass

from travel_plan.agents.client import DeterministicAgentClient, OpenCodeAgentClient
from travel_plan.retrieval.map_client import MockMapClient
from travel_plan.retrieval.weather_client import MockWeatherClient

@dataclass(frozen=True)
class Providers:
    agent: object
    map: object
    weather: object
    agent_runtime: str

class ProviderFactory:
    @staticmethod
    def create(config, executable_finder=shutil.which):
        mode = config.agent_runtime_mode
        executable = executable_finder("opencode")
        if mode == "opencode" and not executable:
            raise RuntimeError("OpenCode was requested but the opencode command was not found")
        use_opencode = mode == "opencode" or (mode == "auto" and bool(executable))
        agent = OpenCodeAgentClient(executable or "opencode") if use_opencode else DeterministicAgentClient(config.mock_reference_date)
        # External providers never follow the Agent runtime mode in the offline demo.
        return Providers(agent, MockMapClient(retrieved_at=config.mock_retrieved_at), MockWeatherClient(), "opencode" if use_opencode else "deterministic")
