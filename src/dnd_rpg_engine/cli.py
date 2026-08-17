# src/dnd_rpg_engine/cli.py
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer

from dnd_rpg_engine.api.platform import create_platform_app
from dnd_rpg_engine.core.commands import AttackCommand, WaitCommand
from dnd_rpg_engine.core.dice import DeterministicDice
from dnd_rpg_engine.core.engine import GameEngine
from dnd_rpg_engine.core.models import (
    ControllerKind,
    Entity,
    EntityKind,
    GameConfig,
    Position,
    ResourcePool,
    TimeMode,
)
from dnd_rpg_engine.core.persistence import SQLiteStore
from dnd_rpg_engine.rulesets.srd_5_2_1 import OFFICIAL_SRD_SOURCE, fetch_official_srd_pdf

app = typer.Typer(help="Deterministic RPG engine CLI.", no_args_is_help=True)


@app.command()
def roll(expression: str, seed: int = 1, stream: str = "cli") -> None:
    """Roll a deterministic dice expression."""
    result = DeterministicDice(seed).roll(expression, stream=stream)
    typer.echo(json.dumps({"rolls": result.rolls, "modifier": result.modifier, "total": result.total}))


@app.command()
def demo(
    mode: TimeMode = TimeMode.HYBRID,
    seconds: float = 20.0,
    timeout: float = 5.0,
) -> None:
    """Run a small headless timeline demo."""
    asyncio.run(_demo(mode, seconds, timeout))


async def _demo(mode: TimeMode, seconds: float, timeout: float) -> None:
    config = GameConfig(
        time_mode=mode,
        seed=42,
        player_decision_timeout_seconds=timeout,
        pause_when_player_ready=True,
    )
    engine = await GameEngine.create("CLI Demo", config=config)
    hero = Entity(
        id="hero",
        name="Hero",
        kind=EntityKind.PLAYER,
        controller=ControllerKind.HUMAN,
        resources=ResourcePool(hp=30, max_hp=30, energy=4, max_energy=4),
        position=Position(area_id="arena", x=0, y=0),
    )
    rival = Entity(
        id="rival",
        name="Clockwork Rival",
        kind=EntityKind.CREATURE,
        controller=ControllerKind.AI,
        resources=ResourcePool(hp=24, max_hp=24),
        position=Position(area_id="arena", x=1, y=0),
        components={"ai": {"target_id": "hero", "action_id": "basic_attack"}},
    )
    await engine.add_entity(hero)
    await engine.add_entity(rival)
    # Process t=0 readiness without advancing actual simulation time.
    await engine.tick(0)
    typer.echo(f"Mode: {mode.value}")
    typer.echo(f"Initial HP: {hero.resources.hp}")
    if mode is TimeMode.TURN_BASED:
        result = await engine.dispatch(WaitCommand(actor_id="hero"))
        for event in result.events:
            typer.echo(f"[{event.simulation_time:6.2f}] {event.type} {event.payload}")
    else:
        step = 0.5
        elapsed = 0.0
        while elapsed < seconds and hero.alive:
            result = await engine.tick(min(step, seconds - elapsed))
            elapsed += step
            for event in result.events:
                typer.echo(f"[{event.simulation_time:6.2f}] {event.type} {event.payload}")
    typer.echo(f"Final HP: {hero.resources.hp}")


@app.command()
def play(mode: TimeMode = TimeMode.HYBRID, timeout: float = 10.0) -> None:
    """Play a minimal local text session. Input is isolated from the event loop."""
    asyncio.run(_play(mode, timeout))


async def _play(mode: TimeMode, timeout: float) -> None:
    config = GameConfig(time_mode=mode, seed=7, player_decision_timeout_seconds=timeout)
    engine = await GameEngine.create("Text Adventure", config=config)
    hero = Entity(
        id="hero",
        name="Hero",
        kind=EntityKind.PLAYER,
        controller=ControllerKind.HUMAN,
        resources=ResourcePool(hp=32, max_hp=32, energy=5, max_energy=5),
        position=Position(area_id="crossroads", x=0, y=0),
    )
    rival = Entity(
        id="rival",
        name="Wandering Rival",
        kind=EntityKind.CREATURE,
        controller=ControllerKind.AI,
        resources=ResourcePool(hp=20, max_hp=20),
        position=Position(area_id="crossroads", x=1, y=0),
        components={"ai": {"target_id": "hero"}},
    )
    await engine.add_entity(hero)
    await engine.add_entity(rival)

    stop = asyncio.Event()
    clock_task: asyncio.Task[None] | None = None
    if config.realtime_enabled:
        clock_task = asyncio.create_task(engine.run_realtime(stop))
    stream = await engine.events.subscribe()

    async def printer() -> None:
        while not stop.is_set():
            event = await stream.get()
            if event.type == "combat.attack_resolved":
                typer.echo(
                    f"\n[t={event.simulation_time:.1f}] action: "
                    f"{event.actor_id} -> {event.target_id}; "
                    f"hit={event.payload['hit']}, impact={event.payload['damage']}"
                )
            elif event.type.startswith("timeline."):
                typer.echo(f"\n[t={event.simulation_time:.1f}] {event.type}")

    printer_task = asyncio.create_task(printer())
    typer.echo("Commands: action, quick, wait, state, quit")
    try:
        while hero.alive and rival.alive:
            line = (await asyncio.to_thread(input, "> ")).strip().lower()
            try:
                if line == "action":
                    await engine.dispatch(AttackCommand(actor_id="hero", target_id="rival"))
                elif line == "quick":
                    await engine.dispatch(AttackCommand(actor_id="hero", target_id="rival", action_id="quick_attack"))
                elif line == "wait":
                    await engine.dispatch(WaitCommand(actor_id="hero"))
                elif line == "state":
                    typer.echo(json.dumps(engine.state_payload(), indent=2, default=str))
                elif line in {"quit", "exit"}:
                    break
            except Exception as exc:
                typer.echo(f"Command rejected: {exc}")
    finally:
        stop.set()
        printer_task.cancel()
        await engine.events.unsubscribe(stream)
        if clock_task:
            clock_task.cancel()
        for task in (printer_task, clock_task):
            if task:
                try:
                    await task
                except asyncio.CancelledError:
                    pass


@app.command("srd-info")
def srd_info() -> None:
    """Show provenance for the bundled opt-in SRD 5.2.1 integration."""
    typer.echo(json.dumps(OFFICIAL_SRD_SOURCE.model_dump(mode="json"), indent=2))


@app.command("fetch-srd")
def fetch_srd(output: Path = Path(".cache/srd/SRD_CC_v5.2.1.pdf")) -> None:
    """Cache the allowlisted official SRD 5.2.1 PDF for local reference."""
    asyncio.run(_fetch_srd(output))


async def _fetch_srd(output: Path) -> None:
    destination = await fetch_official_srd_pdf(output)
    typer.echo(str(destination))


@app.command()
def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    database: str = "rpg_engine.sqlite3",
    advanced: bool = True,
) -> None:
    """Start the complete REST/WebSocket/browser/Creator Studio platform server."""
    import uvicorn

    uvicorn.run(create_platform_app(database, advanced=advanced), host=host, port=port)


@app.command("show-state")
def show_state(campaign_id: str, database: Path = Path("rpg_engine.sqlite3")) -> None:
    """Print a stored SQLite campaign snapshot."""
    asyncio.run(_show_state(campaign_id, database))


async def _show_state(campaign_id: str, database: Path) -> None:
    engine = await GameEngine.load(campaign_id, store=SQLiteStore(database))
    typer.echo(json.dumps(engine.state_payload(), indent=2, default=str))


if __name__ == "__main__":
    app()
