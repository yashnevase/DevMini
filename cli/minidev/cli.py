from __future__ import annotations

from typing import Optional

import typer

from .benchmark import run_benchmark
from .chat import run_acp, run_chat
from .clean import run_clean
from .explain import run_explain
from .health import run_doctor, run_status
from .install import run_install
from .learn import run_learn
from .project import run_init
from .share import run_connect, run_share
from .study import run_study
from .uninstall import run_uninstall

app = typer.Typer(
    name="minidev",
    help="Install and configure Ollama + OpenCode for local coding work.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """MiniDev installs and configures local coding tools."""


@app.command()
def install(
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Override automatic model selection.",
    ),
    profile: str = typer.Option(
        "auto",
        "--profile",
        help="Local model profile to install: auto, low, medium, or max.",
    ),
    all_profiles: bool = typer.Option(
        False,
        "--all-profiles",
        help="Pull every recommended local model profile for this device.",
    ),
    repair: bool = typer.Option(
        False,
        "--repair",
        help="Repair broken Ollama/OpenCode installs if detected.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Assume yes for repair prompts.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what MiniDev would do without changing the system.",
    ),
) -> None:
    """Install missing dependencies, pull a model, and write MiniDev config."""

    run_install(model_override=model, profile=profile, all_profiles=all_profiles, repair=repair, yes=yes, dry_run=dry_run)


@app.command()
def doctor(
    fix: bool = typer.Option(
        False,
        "--fix",
        help="Attempt to repair missing or broken MiniDev dependencies.",
    ),
) -> None:
    """Check Ollama, model, OpenCode, editor, and git readiness."""

    run_doctor(fix=fix)


@app.command()
def status() -> None:
    """Show a compact live MiniDev status view."""

    run_status()


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def chat(ctx: typer.Context) -> None:
    """Open MiniDev chat in the current project."""

    run_chat(list(ctx.args))


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def acp(ctx: typer.Context) -> None:
    """Start MiniDev's Zed/VS Code ACP bridge."""

    run_acp(list(ctx.args))


@app.command()
def share(
    stop: bool = typer.Option(
        False,
        "--stop",
        help="Stop the active LAN share and revoke its token.",
    ),
    port: int = typer.Option(
        4096,
        "--port",
        min=1,
        max=65535,
        help="Preferred OpenCode LAN port.",
    ),
    ollama_port: int = typer.Option(
        11434,
        "--ollama-port",
        min=1,
        max=65535,
        help="Preferred Ollama LAN port.",
    ),
) -> None:
    """Share the OpenCode/Ollama stack on this LAN."""

    run_share(stop=stop, port=port, ollama_port=ollama_port)


@app.command()
def connect(
    endpoint: str = typer.Argument(..., help="Shared OpenCode endpoint, for example 192.168.1.20:4096."),
    token: str = typer.Argument(..., help="Token printed by `minidev share`."),
) -> None:
    """Configure this device to connect to a MiniDev LAN share."""

    run_connect(endpoint=endpoint, token=token)


@app.command()
def benchmark(
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Override the configured benchmark model.",
    ),
) -> None:
    """Measure local Ollama model speed with a fixed short prompt."""

    run_benchmark(model_override=model)


@app.command()
def clean(
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Remove stale references without prompting.",
    ),
) -> None:
    """Remove stale MiniDev file references from index and memory."""

    run_clean(yes=yes)


@app.command()
def explain(
    target: str = typer.Argument(..., help="Path or symbol to explain using .devmini/index.json."),
    model: Optional[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Override the configured explanation model.",
    ),
) -> None:
    """Explain a path or symbol using the MiniDev index and local model."""

    run_explain(target=target, model_override=model)


@app.command()
def uninstall(
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what MiniDev would remove without changing the system.",
    ),
) -> None:
    """Remove only files, packages, and models MiniDev installed."""

    run_uninstall(dry_run=dry_run, yes=yes)


@app.command()
def init(
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite existing MiniDev project context files.",
    ),
) -> None:
    """Create project-specific AGENTS.md, memory.md, and .devmini notes."""

    run_init(force=force)


@app.command()
def learn(
    max_files: int = typer.Option(
        2000,
        "--max-files",
        min=1,
        help="Maximum source files to index.",
    ),
) -> None:
    """Build a lightweight ripgrep + Tree-sitter symbol/import index."""

    run_learn(max_files=max_files)


@app.command()
def study() -> None:
    """Summarize new git-history hotspots and recurring fix patterns."""

    run_study()
