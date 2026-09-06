from __future__ import annotations

from pathlib import Path

import typer
from rich import box
from rich.panel import Panel

from .console import NAVY, badge, console, ok, status_table, title_panel, warn
from .install import model_present
from .manifest import Manifest
from .state import manifest_path
from .system import home_dir, run_command

PROJECT_CONTEXT_FILES = {"project.md", "environment.md", "conventions.md", "decisions.md", "bugs.md", "index.json", "state.json"}
ROOT_CONTEXT_FILES = {"AGENTS.md", "memory.md"}
GLOBAL_CONFIG_FILES = {
    ".config/opencode/opencode.json",
    ".config/zed/settings.json",
}


def run_uninstall(dry_run: bool = False, yes: bool = False) -> None:
    path = manifest_path()
    console.print(title_panel("Uninstalling MiniDev"))

    if not path.exists():
        console.print(Panel("[mini.warn]No MiniDev manifest found.[/]", border_style="mini.box", style=f"on {NAVY}", box=box.ROUNDED))
        return

    manifest = Manifest(path)
    if not yes and not dry_run:
        if not typer.confirm("Remove only files/packages/models recorded as installed by MiniDev?", default=False):
            raise typer.Exit(1)

    table = status_table("Uninstall")
    remove_models(manifest, table, dry_run)
    remove_packages(manifest, table, dry_run)
    remove_files(manifest, table, dry_run)

    if dry_run:
        table.add_row(warn("Dry run"), badge("NO CHANGES", "mini.warn"))

    console.print(table)
    console.print(Panel("[mini.ok]Uninstall complete.[/]", border_style="mini.box", style=f"on {NAVY}", box=box.ROUNDED))


def remove_models(manifest: Manifest, table, dry_run: bool) -> None:
    for item in manifest.data.get("models", []):
        if not isinstance(item, dict) or item.get("action") not in {"pull", "create"}:
            continue
        name = str(item.get("name"))
        provider = item.get("provider")
        if provider != "ollama" or not name:
            continue
        if not model_present(name):
            table.add_row(warn(f"Skipping model {name}"), badge("MISSING", "mini.warn"))
            continue
        run_command(["ollama", "rm", name], dry_run=dry_run)
        table.add_row(ok(f"Removing model {name}"), badge("DRY RUN" if dry_run else "OK", "mini.warn" if dry_run else "mini.ok"))


def remove_packages(manifest: Manifest, table, dry_run: bool) -> None:
    for item in manifest.data.get("packages", []):
        if not isinstance(item, dict) or item.get("action") != "install":
            continue
        name = str(item.get("name"))
        manager = item.get("manager")
        if manager == "brew":
            command = ["brew", "uninstall", name]
        elif manager == "npm":
            command = ["npm", "uninstall", "-g", name]
        elif manager == "vscode":
            command = ["code", "--uninstall-extension", name]
        else:
            continue
        run_command(command, dry_run=dry_run)
        table.add_row(ok(f"Removing package {name}"), badge("DRY RUN" if dry_run else "OK", "mini.warn" if dry_run else "mini.ok"))


def remove_files(manifest: Manifest, table, dry_run: bool) -> None:
    files = [item for item in manifest.data.get("files", []) if isinstance(item, dict)]
    for item in files:
        action = item.get("action")
        if action in {"overwrite", "append"}:
            reason = "OVERWROTE EXISTING" if action == "overwrite" else "APPENDED ONLY"
            table.add_row(warn(f"Skipping {Path(str(item.get('path'))).name}"), badge(reason, "mini.warn"))
            continue
        path = Path(str(item.get("path")))
        if not safe_minidev_file(path):
            table.add_row(warn(f"Skipping {path}"), badge("OUTSIDE MINIDEV", "mini.warn"))
            continue
        if not dry_run and path.exists() and path.is_file():
            path.unlink()
        table.add_row(ok(f"Removing file {path.name}"), badge("DRY RUN" if dry_run else "OK", "mini.warn" if dry_run else "mini.ok"))

    home = manifest_path().parent
    if not dry_run and home.exists() and not any(home.iterdir()):
        home.rmdir()


def safe_minidev_file(path: Path) -> bool:
    try:
        resolved = path.expanduser().resolve()
        root = manifest_path().parent.expanduser().resolve()
    except OSError:
        return False
    if resolved == root / resolved.name and resolved.parent == root:
        return True
    if resolved.parent.name == ".devmini" and resolved.name in PROJECT_CONTEXT_FILES:
        return True
    if resolved.name in ROOT_CONTEXT_FILES and file_has_minidev_marker(resolved):
        return True
    for rel in GLOBAL_CONFIG_FILES:
        if resolved == (home_dir() / rel).expanduser().resolve() and file_has_minidev_marker(resolved):
            return True
    return False


def file_has_minidev_marker(path: Path) -> bool:
    try:
        return "minidev" in path.read_text(errors="replace").lower()
    except OSError:
        return False
