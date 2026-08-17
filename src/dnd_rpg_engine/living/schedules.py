# src/dnd_rpg_engine/living/schedules.py
from __future__ import annotations

from pydantic import BaseModel, Field


class ScheduleEntry(BaseModel):
    start_minute: int = Field(ge=0, lt=1440)
    end_minute: int = Field(gt=0, le=1440)
    location_id: str
    activity: str = "idle"

    def active(self, minute_of_day: int) -> bool:
        if self.start_minute <= self.end_minute:
            return self.start_minute <= minute_of_day < self.end_minute
        return minute_of_day >= self.start_minute or minute_of_day < self.end_minute


class NPCSchedule(BaseModel):
    id: str
    entries: list[ScheduleEntry]

    def current(self, minute_of_day: int) -> ScheduleEntry | None:
        return next((entry for entry in self.entries if entry.active(minute_of_day)), None)


class ScheduleSystem:
    def __init__(self) -> None:
        self.schedules: dict[str, NPCSchedule] = {}
        self.assignments: dict[str, str] = {}

    def register(self, schedule: NPCSchedule) -> None:
        self.schedules[schedule.id] = schedule

    def assign(self, entity_id: str, schedule_id: str) -> None:
        if schedule_id not in self.schedules:
            raise KeyError(schedule_id)
        self.assignments[entity_id] = schedule_id

    def current_for(self, entity_id: str, minute_of_day: int) -> ScheduleEntry | None:
        schedule_id = self.assignments.get(entity_id)
        if schedule_id is None:
            return None
        return self.schedules[schedule_id].current(minute_of_day)
