import asyncio

import typer

app = typer.Typer(name="nimbus", help="Local ambient presence sensing via MCP.", no_args_is_help=True)


@app.command()
def setup() -> None:
    """Install Ollama, pull llama3.2:3b, and write systemd unit files."""
    raise NotImplementedError


@app.command()
def init() -> None:
    """Initialize ~/.nimbus config directory and generate a fresh salt."""
    raise NotImplementedError


@app.command()
def status() -> None:
    """Show collector health and recent observation counts."""
    raise NotImplementedError


@app.command()
def label(
    mac_hash: str = typer.Argument(..., help="Hashed MAC address to label"),
    name: str = typer.Argument(..., help="Human-readable name to assign"),
) -> None:
    """Assign a friendly name to a device."""
    raise NotImplementedError


@app.command()
def ask(
    prompt: str = typer.Argument(..., help="Natural-language question to ask the agent"),
) -> None:
    """Ask the local agent a question about nearby devices."""
    from .agent import ask as _ask
    answer = asyncio.run(_ask(prompt))
    typer.echo(answer)
