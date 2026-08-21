"""Provider assembly is the only boundary affected by mock mode."""
from dataclasses import dataclass

from travel_plan.agents.client import MockAgentClient, OpenCodeAgentClient
from travel_plan.retrieval.map_client import MockMapClient, RealMapClient
from travel_plan.retrieval.weather_client import MockWeatherClient, RealWeatherClient

@dataclass(frozen=True)
class Providers:
    agent: object
    map: object
    weather: object

class ProviderFactory:
    @staticmethod
    def create(config):
        if config.mock_mode:
            return Providers(
                MockAgentClient(config.mock_reference_date),
                MockMapClient(retrieved_at=config.mock_retrieved_at),
                MockWeatherClient(),
            )
        return Providers(OpenCodeAgentClient(),RealMapClient(""),RealWeatherClient(""))
