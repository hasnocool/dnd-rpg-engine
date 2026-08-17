# src/dnd_rpg_engine/core/config.py
from __future__ import annotations

import json
from pathlib import Path

from dnd_rpg_engine.core.models import GameConfig


def load_config(path: str | Path) -> GameConfig:
    return GameConfig.model_validate_json(Path(path).read_text(encoding="utf-8"))


def save_config(config: GameConfig, path: str | Path) -> None:
    Path(path).write_text(json.dumps(config.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
