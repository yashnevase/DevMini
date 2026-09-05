from __future__ import annotations

import json
import subprocess
import time
from dataclasses import asdict
from pathlib import Path
from typing import Callable

import typer
from rich import box
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .console import NAVY, YELLOW, badge, console, fail, ok, status_table, title_panel, warn
from .editor import configure_editor_and_opencode
from .manifest import FileTouch, Manifest, ModelTouch, PackageTouch, now_iso
from .system import CommandStatus, command_status, detect_system, home_dir, pick_model, run_command

MINIDEV_DIR = ".minidev"
CONFIG_NAME = "config.json"
MANIFEST_NAME = "manifest.json"
OLLAMA_MODEL_PROVIDER = "ollama"


def run_install(
    model_override: str | None,
    repair: bool,
    yes: bool,
    dry_run: bool,
) -> None:
    system_info = detect_system()
    selected_model = model_override or pick_model(system_info.ram_gb)
    minidev_dir = home_dir() / MINIDEV_DIR
    config_path = minidev_dir / CONFIG_NAME
    manifest_path = minidev_dir / MANIFEST_NAME
    manifest = Manifest(manifest_path)

    console.print(title_panel("Installing MiniDev..."))
    console.print(model_panel(selected_model, system_info.ram_gb))

    table = status_table("System Check")
    table.add_row(ok("Detected system"), badge(system_info.os_name))
    table.add_row(ok("Checking RAM"), badge(f"{system_info.ram_gb:g} GB", "mini.yellow"))

    ollama = ensure_tool(
        command="ollama",
        display_name="Ollama",
        install_plan=lambda action: ollama_install_plan(system_info.os_name, action),
        manifest=manifest,
        repair=repair,
        yes=yes,
        dry_run=dry_run,
        table=table,
    )

    opencode = ensure_tool(
        command="opencode",
        display_name="OpenCode",
        install_plan=opencode_install_plan,
        manifest=manifest,
        repair=repair,
        yes=yes,
        dry_run=dry_run,
        table=table,
    )

    ensure_ollama_ready(table, dry_run=dry_run)
    pull_model(selected_model, manifest, table, dry_run=dry_run)
    write_config(config_path, selected_model, system_info, ollama, opencode, manifest, table, dry_run)
    configure_editor_and_opencode(manifest, table, dry_run=dry_run)
    manifest.record_file(FileTouch(str(manifest_path), "MiniDev uninstall manifest", "write"))
    manifest.save(dry_run=dry_run)

    if dry_run:
        table.add_row(warn("Dry run"), badge("NO CHANGES", "mini.warn"))

    console.print(table)
    console.print(
        Panel(
            "[mini.ok]Done![/]\n[mini.yellow]MiniDev is ready to assist you.[/]",
            border_style="mini.box",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )


def ensure_tool(
    command: str,
    display_name: str,
    install_plan: Callable[[str], tuple[list[list[str]], PackageTouch]],
    manifest: Manifest,
    repair: bool,
    yes: bool,
    dry_run: bool,
    table: Table,
) -> CommandStatus:
    status = command_status(command)
    if status.installed and status.working:
        label = status.version or status.path or "installed"
        table.add_row(ok(display_name), badge(label))
        return status

    if status.installed and not status.working:
        table.add_row(warn(f"{display_name} found but broken"), badge("REPAIR?", "mini.warn"))
        if not should_repair(display_name, repair=repair, yes=yes):
            raise typer.Exit(1)
        action = "repair"
    else:
        action = "install"

    if not status.installed:
        table.add_row(warn(f"{display_name} missing"), badge("INSTALL", "mini.warn"))

    install_steps, package = install_plan(action)
    for step in install_steps:
        run_command(step, dry_run=dry_run)

    manifest.record_package(package)
    repaired = command_status(command) if not dry_run else status
    if not dry_run and not repaired.working:
        table.add_row(fail(display_name), badge("FAILED", "mini.err"))
        raise typer.BadParameter(f"{display_name} did not verify after installation.")

    table.add_row(
        ok(f"Installing {display_name}"),
        badge("DRY RUN" if dry_run else "OK", "mini.warn" if dry_run else "mini.ok"),
    )
    return repaired


def should_repair(display_name: str, repair: bool, yes: bool) -> bool:
    if repair or yes:
        return True
    return typer.confirm(f"{display_name} is installed but not working. Repair it?", default=True)


def ollama_install_plan(os_name: str, action: str) -> tuple[list[list[str]], PackageTouch]:
    if os_name not in {"Darwin", "Linux"}:
        raise typer.BadParameter("MiniDev install currently supports Ollama installation with Homebrew on macOS/Linux.")
    ensure_manager("brew", "Homebrew is required to install Ollama.")
    brew_action = "reinstall" if action == "repair" else "install"
    return [["brew", brew_action, "ollama"]], PackageTouch("ollama", "brew", brew_action)


def opencode_install_plan(action: str) -> tuple[list[list[str]], PackageTouch]:
    if command_status("brew").working:
        brew_action = "reinstall" if action == "repair" else "install"
        package_name = "anomalyco/tap/opencode"
        return [["brew", brew_action, package_name]], PackageTouch(package_name, "brew", brew_action)
    ensure_manager("npm", "Homebrew or npm is required to install OpenCode.")
    return [["npm", "install", "-g", "opencode-ai"]], PackageTouch("opencode-ai", "npm", "install")


def ensure_manager(command: str, message: str) -> None:
    if not command_status(command).working:
        raise typer.BadParameter(message)


def ensure_ollama_ready(table: Table, dry_run: bool) -> None:
    if dry_run:
        table.add_row(ok("Starting Ollama"), badge("DRY RUN", "mini.warn"))
        return

    if ollama_list_works():
        table.add_row(ok("Ollama service"), badge("RUNNING"))
        return

    started = False
    if command_status("brew").working:
        try:
            subprocess.run(
                ["brew", "services", "start", "ollama"],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            started = True
        except (OSError, subprocess.SubprocessError):
            started = False

    if not started:
        try:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError:
            pass

    for _ in range(20):
        if ollama_list_works():
            table.add_row(ok("Ollama service"), badge("RUNNING"))
            return
        time.sleep(0.5)

    table.add_row(fail("Ollama service"), badge("FAILED", "mini.err"))
    raise typer.BadParameter("Ollama is installed, but MiniDev could not start or reach the Ollama service.")


def ollama_list_works() -> bool:
    try:
        proc = subprocess.run(["ollama", "list"], check=False, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def pull_model(model: str, manifest: Manifest, table: Table, dry_run: bool) -> None:
    if model_present(model):
        manifest.record_model(ModelTouch(model, OLLAMA_MODEL_PROVIDER, "present"))
        table.add_row(ok(f"Model {model}"), badge("PRESENT"))
        return

    run_command(["ollama", "pull", model], dry_run=dry_run)
    manifest.record_model(ModelTouch(model, OLLAMA_MODEL_PROVIDER, "pull"))
    table.add_row(
        ok(f"Pulling model {model}"),
        badge("DRY RUN" if dry_run else "OK", "mini.warn" if dry_run else "mini.ok"),
    )


def model_present(model: str) -> bool:
    try:
        proc = subprocess.run(["ollama", "list"], check=False, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return False
    if proc.returncode != 0:
        return False
    names = {line.split()[0] for line in proc.stdout.splitlines()[1:] if line.split()}
    return model in names


def write_config(
    config_path: Path,
    model: str,
    system_info: object,
    ollama: CommandStatus,
    opencode: CommandStatus,
    manifest: Manifest,
    table: Table,
    dry_run: bool,
) -> None:
    config = {
        "version": __version__,
        "installed_at": now_iso(),
        "model": model,
        "provider": OLLAMA_MODEL_PROVIDER,
        "paths": {
            "minidev_home": str(config_path.parent),
            "config": str(config_path),
            "manifest": str(config_path.parent / MANIFEST_NAME),
        },
        "system": asdict(system_info),
        "tools": {
            "ollama": command_payload(ollama),
            "opencode": command_payload(opencode),
        },
        "runtime": {
            "agent": "opencode",
            "tool_executor": "opencode",
            "miniDevRole": "install_configure_write_files_only",
        },
    }

    manifest.record_file(FileTouch(str(config_path), "MiniDev runtime configuration", "write"))
    if not dry_run:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config, indent=2) + "\n")
    table.add_row(
        ok("Writing config"),
        badge("DRY RUN" if dry_run else "OK", "mini.warn" if dry_run else "mini.ok"),
    )


def command_payload(status: CommandStatus) -> dict[str, object]:
    return {
        "path": status.path,
        "version": status.version,
        "installed": status.installed,
        "working": status.working,
    }


def model_panel(model: str, ram_gb: float) -> Panel:
    body = (
        f"[mini.yellow]MODEL SELECTED[/]\n"
        f"[mini.blue]{model}[/]\n\n"
        f"[mini.text]Best for your[/]\n"
        f"[mini.yellow]{ram_gb:g} GB RAM[/]"
    )
    return Panel(body, border_style=YELLOW, style=f"on {NAVY}", box=box.ROUNDED, padding=(1, 2))
