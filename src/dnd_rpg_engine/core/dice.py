# src/dnd_rpg_engine/core/dice.py
from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass

_DICE_RE = re.compile(r"^\s*(?:(\d*)d(\d+))?\s*([+-]\s*\d+)?\s*$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class DiceResult:
    expression: str
    rolls: tuple[int, ...]
    modifier: int
    total: int


class DeterministicDice:
    """Independent deterministic RNG streams with serializable counters."""

    def __init__(self, seed: int, counters: dict[str, int] | None = None) -> None:
        self.seed = seed
        self._counters = dict(counters or {})

    @property
    def counters(self) -> dict[str, int]:
        return dict(self._counters)

    def _rng(self, stream: str) -> random.Random:
        counter = self._counters.get(stream, 0)
        material = f"{self.seed}:{stream}:{counter}".encode()
        digest = hashlib.sha256(material).digest()
        self._counters[stream] = counter + 1
        return random.Random(int.from_bytes(digest[:16], "big"))

    def roll(self, expression: str, *, stream: str = "default") -> DiceResult:
        match = _DICE_RE.match(expression)
        if not match:
            raise ValueError(f"invalid dice expression: {expression!r}")
        count_text, sides_text, modifier_text = match.groups()
        count = int(count_text or 1) if sides_text else 0
        sides = int(sides_text or 0)
        modifier = int((modifier_text or "0").replace(" ", ""))
        if count < 0 or count > 100 or sides < 0 or sides > 10000:
            raise ValueError("dice expression exceeds safe limits")
        if count and sides < 2:
            raise ValueError("dice must have at least 2 sides")
        rng = self._rng(stream)
        rolls = tuple(rng.randint(1, sides) for _ in range(count))
        return DiceResult(expression, rolls, modifier, sum(rolls) + modifier)

    def d20(self, *, stream: str = "checks") -> int:
        return self.roll("1d20", stream=stream).total
