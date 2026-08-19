from dataclasses import dataclass
from datetime import date
from typing import Protocol

@dataclass(frozen=True)
class Forecast:
    date: str; condition: str; precipitation_probability: int; source: str

class WeatherClient(Protocol):
    def get_forecast(self, city: str, day: date) -> Forecast: ...

class MockWeatherClient:
    def __init__(self, forecasts: dict[str, dict] | None=None): self.forecasts=forecasts or {}
    def get_forecast(self, city: str, day: date) -> Forecast:
        raw=self.forecasts.get(day.isoformat(), {"condition":"clear","precipitation_probability":10})
        return Forecast(day.isoformat(),raw["condition"],raw["precipitation_probability"],"mock_weather")

class RealWeatherClient:
    def __init__(self, api_key: str): self.api_key=api_key
    def get_forecast(self, city: str, day: date) -> Forecast: raise RuntimeError("Real weather provider endpoint is not configured")

