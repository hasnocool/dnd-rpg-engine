# src/dnd_rpg_engine/living/time.py
from __future__ import annotations

from pydantic import BaseModel, Field


class WorldTime(BaseModel):
    total_minutes: float = Field(default=0.0, ge=0)
    minutes_per_day: int = Field(default=1440, ge=1)

    @property
    def day(self) -> int:
        return int(self.total_minutes // self.minutes_per_day) + 1

    @property
    def minute_of_day(self) -> int:
        return int(self.total_minutes % self.minutes_per_day)

    @property
    def hour(self) -> int:
        return self.minute_of_day // 60

    @property
    def minute(self) -> int:
        return self.minute_of_day % 60

    def advance(self, minutes: float) -> None:
        if minutes < 0:
            raise ValueError("world time cannot move backward")
        self.total_minutes += minutes

    def display(self) -> str:
        return f"Day {self.day}, {self.hour:02d}:{self.minute:02d}"
