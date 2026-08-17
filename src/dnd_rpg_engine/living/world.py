# src/dnd_rpg_engine/living/world.py
from __future__ import annotations

from dataclasses import dataclass

from dnd_rpg_engine.core.dice import DeterministicDice
from dnd_rpg_engine.living.dynamic_events import DynamicEventDefinition, DynamicEventSystem
from dnd_rpg_engine.living.economy import EconomySystem
from dnd_rpg_engine.living.factions import FactionSystem
from dnd_rpg_engine.living.schedules import ScheduleSystem
from dnd_rpg_engine.living.time import WorldTime
from dnd_rpg_engine.living.weather import Weather, WeatherSystem


@dataclass(slots=True)
class WorldAdvance:
    previous_minutes: float
    current_minutes: float
    weather_before: Weather
    weather_after: Weather
    dynamic_events: list[DynamicEventDefinition]


class LivingWorld:
    def __init__(self, dice: DeterministicDice, start_minutes: float = 0.0) -> None:
        self.clock = WorldTime(total_minutes=start_minutes)
        self.weather = WeatherSystem(dice)
        self.factions = FactionSystem()
        self.schedules = ScheduleSystem()
        self.economy = EconomySystem()
        self.dynamic_events = DynamicEventSystem()

    def advance(self, minutes: float, state) -> WorldAdvance:
        before = self.clock.total_minutes
        weather_before = self.weather.current
        self.clock.advance(minutes)
        weather_after = self.weather.advance(self.clock.total_minutes)
        dynamic = self.dynamic_events.evaluate(state)
        return WorldAdvance(before, self.clock.total_minutes, weather_before, weather_after, dynamic)
