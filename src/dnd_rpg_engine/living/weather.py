# src/dnd_rpg_engine/living/weather.py
from __future__ import annotations

from enum import StrEnum

from dnd_rpg_engine.core.dice import DeterministicDice


class Weather(StrEnum):
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAIN = "rain"
    STORM = "storm"
    FOG = "fog"
    SNOW = "snow"


class WeatherSystem:
    TRANSITIONS: dict[Weather, tuple[Weather, ...]] = {
        Weather.CLEAR: (Weather.CLEAR, Weather.CLEAR, Weather.CLOUDY, Weather.FOG),
        Weather.CLOUDY: (Weather.CLEAR, Weather.CLOUDY, Weather.CLOUDY, Weather.RAIN),
        Weather.RAIN: (Weather.CLOUDY, Weather.RAIN, Weather.RAIN, Weather.STORM),
        Weather.STORM: (Weather.RAIN, Weather.CLOUDY, Weather.STORM),
        Weather.FOG: (Weather.CLEAR, Weather.CLOUDY, Weather.FOG),
        Weather.SNOW: (Weather.CLOUDY, Weather.SNOW, Weather.SNOW),
    }

    def __init__(self, dice: DeterministicDice, initial: Weather = Weather.CLEAR) -> None:
        self.dice = dice
        self.current = initial
        self.last_change_world_minute = 0.0

    def advance(self, world_minute: float, *, interval: float = 180.0) -> Weather:
        if world_minute - self.last_change_world_minute < interval:
            return self.current
        options = self.TRANSITIONS[self.current]
        roll = self.dice.roll(f"1d{len(options)}", stream="weather").total - 1
        self.current = options[roll]
        self.last_change_world_minute = world_minute
        return self.current
