from __future__ import annotations

import os

import typer

from dnd_rpg_engine.api.platform import create_platform_app

app = typer.Typer(help="Production RPG platform API server.", no_args_is_help=False)


@app.command()
def run(
    database_url: str | None = typer.Option(
        default=None,
        help="SQLite path or PostgreSQL DSN. Defaults to RPG_DATABASE_URL or rpg_engine.sqlite3.",
    ),
    host: str = typer.Option(default="127.0.0.1"),
    port: int = typer.Option(default=8000, min=1, max=65535),
    advanced: bool = typer.Option(default=True, help="Use AdvancedGameEngine for the complete v1.2-v2.5 profile."),
) -> None:
    """Serve the complete v2.5 platform API and browser clients.

    Authentication, signing secrets, and bootstrap provisioning are controlled
    by RPG_AUTH_REQUIRED, RPG_AUTH_SECRET, and RPG_BOOTSTRAP_KEY. Production
    deployments should use PostgreSQL, TLS at the ingress/reverse proxy, and a
    secret manager rather than command-line secrets.
    """
    import uvicorn

    resolved_database = database_url or os.environ.get("RPG_DATABASE_URL", "rpg_engine.sqlite3")
    uvicorn.run(create_platform_app(resolved_database, advanced=advanced), host=host, port=port)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
