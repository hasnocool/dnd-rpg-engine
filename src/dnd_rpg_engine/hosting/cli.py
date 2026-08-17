# src/dnd_rpg_engine/hosting/cli.py
from __future__ import annotations

import asyncio
import os
import signal

import typer

from dnd_rpg_engine.hosting.postgres import PostgreSQLStore
from dnd_rpg_engine.hosting.workers import SimulationWorker, WorkerConfig

app = typer.Typer(help="Production RPG simulation worker.", no_args_is_help=False)


@app.command()
def run(
    database_url: str | None = typer.Option(
        default=None,
        help="PostgreSQL DSN. Defaults to RPG_DATABASE_URL.",
    ),
    capacity: int | None = typer.Option(
        default=None,
        min=1,
        help="Maximum campaigns hosted by this worker. Defaults to RPG_WORKER_CAPACITY or 16.",
    ),
    worker_id: str | None = typer.Option(default=None),
) -> None:
    """Run a lease-backed campaign simulation worker."""
    resolved_database = database_url or os.environ.get("RPG_DATABASE_URL", "")
    resolved_capacity = capacity if capacity is not None else int(os.environ.get("RPG_WORKER_CAPACITY", "16"))
    if not resolved_database.startswith(("postgres://", "postgresql://")):
        raise typer.BadParameter("production workers require a PostgreSQL database URL")
    asyncio.run(_run(resolved_database, capacity=resolved_capacity, worker_id=worker_id))


async def _run(database_url: str, *, capacity: int, worker_id: str | None) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass

    store = PostgreSQLStore(database_url)
    config_kwargs: dict[str, object] = {"capacity": capacity}
    if worker_id:
        config_kwargs["worker_id"] = worker_id
    worker = SimulationWorker(store, WorkerConfig(**config_kwargs))
    try:
        await worker.run(stop)
    finally:
        await store.close()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
