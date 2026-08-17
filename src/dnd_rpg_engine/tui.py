# src/dnd_rpg_engine/tui.py
from __future__ import annotations

import asyncio

from dnd_rpg_engine.core.commands import AttackCommand, WaitCommand
from dnd_rpg_engine.core.engine import GameEngine
from dnd_rpg_engine.core.models import ControllerKind, Entity, EntityKind, GameConfig, Position, ResourcePool, TimeMode


def main() -> None:
    try:
        from textual.app import App, ComposeResult
        from textual.containers import Horizontal, Vertical
        from textual.widgets import Button, Footer, Header, Input, Log, Static
    except ImportError as exc:
        raise SystemExit("Install the TUI extra: pip install 'dnd-rpg-engine[tui]'") from exc

    class RPGTUI(App):
        CSS = """
        Screen { layout: vertical; }
        #main { height: 1fr; }
        #state { width: 38%; border: round $primary; padding: 1; }
        #log { width: 62%; border: round $secondary; }
        #commands { height: auto; padding: 1; }
        Button { margin-right: 1; }
        """

        def __init__(self) -> None:
            super().__init__()
            self.engine: GameEngine | None = None
            self.clock_stop = asyncio.Event()
            self.clock_task: asyncio.Task[None] | None = None
            self.stream_task: asyncio.Task[None] | None = None

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with Horizontal(id="main"):
                yield Static("Starting…", id="state")
                yield Log(id="log", highlight=True, auto_scroll=True)
            with Vertical(id="commands"):
                with Horizontal():
                    yield Button("Basic action", id="attack")
                    yield Button("Quick action", id="quick")
                    yield Button("Wait", id="wait")
                yield Input(placeholder="Enter: action | quick | wait", id="command")
            yield Footer()

        async def on_mount(self) -> None:
            config = GameConfig(time_mode=TimeMode.HYBRID, seed=12, player_decision_timeout_seconds=8)
            self.engine = await GameEngine.create("TUI Campaign", config=config)
            await self.engine.add_entity(
                Entity(
                    id="hero",
                    name="Hero",
                    kind=EntityKind.PLAYER,
                    controller=ControllerKind.HUMAN,
                    resources=ResourcePool(hp=30, max_hp=30, energy=5, max_energy=5),
                    position=Position(area_id="field", x=0, y=0),
                )
            )
            await self.engine.add_entity(
                Entity(
                    id="rival",
                    name="Clockwork Rival",
                    kind=EntityKind.CREATURE,
                    controller=ControllerKind.AI,
                    resources=ResourcePool(hp=24, max_hp=24),
                    position=Position(area_id="field", x=1, y=0),
                    components={"ai": {"target_id": "hero"}},
                )
            )
            stream = await self.engine.events.subscribe()

            async def consume() -> None:
                log = self.query_one("#log", Log)
                while True:
                    event = await stream.get()
                    log.write_line(f"[{event.simulation_time:7.2f}] {event.type} {event.payload}")
                    self.refresh_state()

            self.stream_task = asyncio.create_task(consume())
            self.clock_task = asyncio.create_task(self.engine.run_realtime(self.clock_stop))
            self.set_interval(0.2, self.refresh_state)
            self.refresh_state()

        def refresh_state(self) -> None:
            if not self.engine:
                return
            hero = self.engine.state.entities.get("hero")
            rival = self.engine.state.entities.get("rival")
            payload = self.engine.state_payload()
            text = (
                f"Mode: {payload['time_mode']}\n"
                f"Simulation: {payload['campaign']['simulation_time']:.2f}s\n"
                f"World: {payload['world_time']}\n"
                f"Weather: {payload['weather']}\n"
                f"Ready: {', '.join(payload['ready_humans']) or '—'}\n"
                f"Decision window: {payload['decision_pause_remaining']}\n\n"
                f"Hero: {hero.resources.hp if hero else 0}/{hero.resources.max_hp if hero else 0} HP\n"
                f"Rival: {rival.resources.hp if rival else 0}/{rival.resources.max_hp if rival else 0} HP"
            )
            self.query_one("#state", Static).update(text)

        async def act(self, kind: str) -> None:
            if not self.engine:
                return
            try:
                if kind == "action":
                    await self.engine.dispatch(AttackCommand(actor_id="hero", target_id="rival"))
                elif kind == "quick":
                    await self.engine.dispatch(AttackCommand(actor_id="hero", target_id="rival", action_id="quick_attack"))
                elif kind == "wait":
                    await self.engine.dispatch(WaitCommand(actor_id="hero"))
            except Exception as exc:
                self.query_one("#log", Log).write_line(f"REJECTED: {exc}")

        async def on_button_pressed(self, event: Button.Pressed) -> None:
            mapping = {"attack": "action", "quick": "quick", "wait": "wait"}
            if event.button.id in mapping:
                await self.act(mapping[event.button.id])

        async def on_input_submitted(self, event: Input.Submitted) -> None:
            await self.act(event.value.strip().lower())
            event.input.value = ""

        async def on_unmount(self) -> None:
            self.clock_stop.set()
            for task in (self.clock_task, self.stream_task):
                if task:
                    task.cancel()

    RPGTUI().run()


if __name__ == "__main__":
    main()
