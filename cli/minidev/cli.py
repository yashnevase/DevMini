from __future__ import annotations

from typing import Optional

import typer

from .health import run_doctor, run_status
from .install import run_install
from .learn import run_learn
from .project import run_init
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

    run_install(model_override=model, repair=repair, yes=yes, dry_run=dry_run)


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
