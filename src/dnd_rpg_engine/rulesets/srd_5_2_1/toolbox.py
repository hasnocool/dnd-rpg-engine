# src/dnd_rpg_engine/rulesets/srd_5_2_1/toolbox.py
from __future__ import annotations

from collections.abc import Iterable
from fractions import Fraction
import math

from dnd_rpg_engine.rulesets.srd_5_2_1.extended_models import (
    EncounterBudgetDefinition,
    EncounterCandidate,
    EnvironmentalRule,
    TerrainTravelRule,
    TravelPaceDefinition,
)


TRAVEL_PACES: dict[str, TravelPaceDefinition] = {
    "fast": TravelPaceDefinition(id="fast", feet_per_minute=400, miles_per_hour=4, miles_per_day=30, perception_survival_mode="disadvantage", stealth_mode="disadvantage"),
    "normal": TravelPaceDefinition(id="normal", feet_per_minute=300, miles_per_hour=3, miles_per_day=24, stealth_mode="disadvantage"),
    "slow": TravelPaceDefinition(id="slow", feet_per_minute=200, miles_per_hour=2, miles_per_day=18, perception_survival_mode="advantage"),
}


TERRAIN_TRAVEL_RULES: dict[str, TerrainTravelRule] = {
    row.id: row
    for row in (
        TerrainTravelRule(id="arctic", pace="fast", encounter_distance="6d6 * 10 ft", foraging_dc=20, navigation_dc=10, search_dc=10),
        TerrainTravelRule(id="coastal", pace="normal", encounter_distance="2d10 * 10 ft", foraging_dc=10, navigation_dc=5, search_dc=15),
        TerrainTravelRule(id="desert", pace="normal", encounter_distance="6d6 * 10 ft", foraging_dc=20, navigation_dc=10, search_dc=10),
        TerrainTravelRule(id="forest", pace="normal", encounter_distance="2d8 * 10 ft", foraging_dc=10, navigation_dc=15, search_dc=15),
        TerrainTravelRule(id="grassland", pace="fast", encounter_distance="6d6 * 10 ft", foraging_dc=15, navigation_dc=5, search_dc=15),
        TerrainTravelRule(id="hill", pace="normal", encounter_distance="2d10 * 10 ft", foraging_dc=15, navigation_dc=10, search_dc=15),
        TerrainTravelRule(id="mountain", pace="slow", encounter_distance="4d10 * 10 ft", foraging_dc=20, navigation_dc=15, search_dc=20),
        TerrainTravelRule(id="swamp", pace="slow", encounter_distance="2d8 * 10 ft", foraging_dc=10, navigation_dc=15, search_dc=20),
    )
}


ENVIRONMENTAL_RULES: dict[str, EnvironmentalRule] = {
    "extended_travel": EnvironmentalRule(id="extended_travel", name="Extended Travel", check_ability="constitution", dc=10, interval_seconds=3600, consequence="exhaustion", tags=("dc_increases_each_extra_hour",), source_page=192),
    "deep_water": EnvironmentalRule(id="deep_water", name="Deep Water", check_ability="constitution", dc=10, interval_seconds=3600, consequence="exhaustion", tags=("swim_speed_exempts", "depth_over_100_ft"), source_page=195),
    "extreme_cold": EnvironmentalRule(id="extreme_cold", name="Extreme Cold", check_ability="constitution", dc=10, interval_seconds=3600, consequence="exhaustion", tags=("cold_resistance_exempts", "cold_immunity_exempts", "temperature_0f_or_lower"), source_page=195),
    "extreme_heat": EnvironmentalRule(id="extreme_heat", name="Extreme Heat", check_ability="constitution", consequence="exhaustion", tags=("temperature_100f_or_higher",), source_page=195),
    "frigid_water": EnvironmentalRule(id="frigid_water", name="Frigid Water", check_ability="constitution", dc=10, consequence="exhaustion", tags=("cold_resistance_exempts", "cold_immunity_exempts", "grace_minutes_equal_constitution_score"), source_page=195),
    "heavy_precipitation": EnvironmentalRule(id="heavy_precipitation", name="Heavy Precipitation", consequence="perception_disadvantage", tags=("lightly_obscured", "open_flames_extinguished_by_heavy_rain"), source_page=195),
    "high_altitude": EnvironmentalRule(id="high_altitude", name="High Altitude", consequence="travel_time_counts_double", tags=("altitude_10000_ft_or_higher", "acclimation_supported"), source_page=195),
    "slippery_ice": EnvironmentalRule(id="slippery_ice", name="Slippery Ice", check_ability="dexterity", dc=10, consequence="prone", tags=("difficult_terrain", "check_on_enter_or_turn_start"), source_page=195),
    "strong_wind": EnvironmentalRule(id="strong_wind", name="Strong Wind", consequence="flight_must_end_grounded", tags=("open_flames_extinguished", "fog_dispersed", "sandstorm_perception_disadvantage"), source_page=195),
}


_ENCOUNTER_ROWS = (
    (1, 50, 75, 100), (2, 100, 150, 200), (3, 150, 225, 400), (4, 250, 375, 500),
    (5, 500, 750, 1100), (6, 600, 1000, 1400), (7, 750, 1300, 1700), (8, 1000, 1700, 2100),
    (9, 1300, 2000, 2600), (10, 1600, 2300, 3100), (11, 1900, 2900, 4100), (12, 2200, 3700, 4700),
    (13, 2600, 4200, 5400), (14, 2900, 4900, 6200), (15, 3300, 5400, 7800), (16, 3800, 6100, 9800),
    (17, 4500, 7200, 11700), (18, 5000, 8700, 14200), (19, 5500, 10700, 17200), (20, 6400, 13200, 22000),
)
ENCOUNTER_BUDGETS = {
    level: EncounterBudgetDefinition(level=level, low=low, moderate=moderate, high=high)
    for level, low, moderate, high in _ENCOUNTER_ROWS
}

CR_XP: dict[str, int] = {
    "0": 10,
    "1/8": 25,
    "1/4": 50,
    "1/2": 100,
    "1": 200,
    "2": 450,
    "3": 700,
    "4": 1100,
    "5": 1800,
    "6": 2300,
    "7": 2900,
    "8": 3900,
    "9": 5000,
    "10": 5900,
    "11": 7200,
    "12": 8400,
    "13": 10000,
    "14": 11500,
    "15": 13000,
    "16": 15000,
    "17": 18000,
    "18": 20000,
    "19": 22000,
    "20": 25000,
    "21": 33000,
    "22": 41000,
    "23": 50000,
    "24": 62000,
    "25": 75000,
    "26": 90000,
    "27": 105000,
    "28": 120000,
    "29": 135000,
    "30": 155000,
}


def encounter_budget(party_levels: Iterable[int], difficulty: str = "moderate") -> int:
    if difficulty not in {"low", "moderate", "high"}:
        raise ValueError("difficulty must be low, moderate, or high")
    total = 0
    for level in party_levels:
        try:
            row = ENCOUNTER_BUDGETS[int(level)]
        except (KeyError, ValueError) as exc:
            raise ValueError("party levels must be integers from 1 through 20") from exc
        total += int(getattr(row, difficulty))
    return total


def monster_xp(challenge_rating: str | int | float) -> int:
    key = _normalize_cr(challenge_rating)
    if key not in CR_XP:
        raise ValueError(f"unsupported challenge rating: {challenge_rating}")
    return CR_XP[key]


def special_travel_rate(speed_feet: int, *, hours: float = 8.0, pace: str = "normal") -> dict[str, float]:
    if speed_feet <= 0 or hours <= 0:
        raise ValueError("speed_feet and hours must be positive")
    base_mph = speed_feet / 10.0
    multipliers = {"fast": Fraction(4, 3), "normal": Fraction(1, 1), "slow": Fraction(2, 3)}
    if pace not in multipliers:
        raise ValueError("pace must be fast, normal, or slow")
    normal_day = base_mph * hours
    miles_per_day = math.floor(normal_day * float(multipliers[pace]))
    return {"miles_per_hour": base_mph, "miles_per_day": float(miles_per_day)}


def extended_travel_dc(extra_hour_number: int) -> int:
    if extra_hour_number < 1:
        raise ValueError("extra_hour_number must be at least 1")
    return 10 + extra_hour_number


def build_encounter_candidate(
    monsters: Iterable[tuple[str, str | int | float]],
    party_levels: Iterable[int],
    *,
    difficulty: str = "moderate",
) -> EncounterCandidate:
    budget = encounter_budget(party_levels, difficulty)
    selected: list[str] = []
    total = 0
    for monster_id, cr in sorted(monsters, key=lambda row: (monster_xp(row[1]), row[0]), reverse=True):
        xp = monster_xp(cr)
        if total + xp <= budget:
            selected.append(monster_id)
            total += xp
    utilization = 0.0 if budget == 0 else total / budget
    return EncounterCandidate(monster_ids=tuple(selected), total_xp=total, budget=budget, utilization=utilization)


def _normalize_cr(value: str | int | float) -> str:
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        fraction_map = {0.125: "1/8", 0.25: "1/4", 0.5: "1/2"}
        if value in fraction_map:
            return fraction_map[value]
        if value.is_integer():
            return str(int(value))
    return str(value).strip()
