from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
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
from .model_catalog import AUTO, MAX, model_candidates, pick_profile_model, profile_models
from .model_capability import check_structured_tool_calls
from .system import CommandStatus, command_status, detect_system, home_dir, run_command

MINIDEV_DIR = ".minidev"
CONFIG_NAME = "config.json"
MANIFEST_NAME = "manifest.json"
OLLAMA_MODEL_PROVIDER = "ollama"
MODEL_PULL_TIMEOUT_SECONDS = 60 * 120
MODEL_DISK_BUFFER_GB = 2.0
MINIDEV_CONTEXT_TOKENS = 16384
MINIDEV_MODEL_PREFIX = "minidev-"


def run_install(
    model_override: str | None,
    profile: str,
    all_profiles: bool,
    repair: bool,
    yes: bool,
    dry_run: bool,
) -> None:
    system_info = detect_system()
    profiles = profile_models(system_info)
    candidates = model_candidates(system_info)
    selected_profile = MAX if profile == AUTO else profile.lower()
    try:
        selected_base_model = model_override or pick_profile_model(system_info, profile)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    minidev_dir = home_dir() / MINIDEV_DIR
    config_path = minidev_dir / CONFIG_NAME
    manifest_path = minidev_dir / MANIFEST_NAME
    manifest = Manifest(manifest_path)

    console.print(title_panel("Installing MiniDev..."))
    console.print(model_panel(selected_base_model, system_info.ram_gb, candidates))

    table = status_table("System Check")
    table.add_row(ok("Detected system"), badge(system_info.os_name))
    table.add_row(ok("Checking RAM"), badge(f"{system_info.ram_gb:g} GB", "mini.yellow"))

    models_to_pull = profile_pull_list(profiles, selected_base_model, all_profiles=all_profiles)
    confirm_first_run_plan(models_to_pull, profiles, yes=yes, dry_run=dry_run)

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
    for model in models_to_pull:
        pull_model(model, profiles, manifest, table, dry_run=dry_run)
    selected_model = ensure_context_model(selected_base_model, manifest, table, dry_run=dry_run)
    model_tools_ok = check_model_tools(selected_model, table, dry_run=dry_run)
    editor_name = configure_editor_and_opencode(
        manifest,
        table,
        dry_run=dry_run,
        model=selected_model,
        tool_calls=model_tools_ok,
    )
    write_config(
        config_path,
        selected_model,
        selected_base_model,
        selected_profile,
        profiles,
        candidates,
        model_tools_ok,
        system_info,
        ollama,
        opencode,
        editor_name,
        manifest,
        table,
        dry_run,
    )
    manifest.record_file(FileTouch(str(manifest_path), "MiniDev uninstall manifest", "write"))
    prune_missing_pulled_models(manifest)
    manifest.save(dry_run=dry_run)

    if dry_run:
        table.add_row(warn("Dry run"), badge("NO CHANGES", "mini.warn"))

    console.print(table)
    done_text = "[mini.ok]Done![/]\n[mini.yellow]MiniDev is ready to assist you.[/]"
    if not dry_run and not model_tools_ok:
        done_text = (
            "[mini.warn]Installed with warning.[/]\n"
            "[mini.text]Local chat works, but OpenCode file tools need a model with structured tool-call support.[/]"
        )
    console.print(
        Panel(
            done_text,
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


def pull_model(model: str, profiles: dict[str, object], manifest: Manifest, table: Table, dry_run: bool) -> None:
    if model_present(model):
        manifest.record_model(ModelTouch(model, OLLAMA_MODEL_PROVIDER, "present"))
        table.add_row(ok(f"Model {model}"), badge("PRESENT"))
        return

    if dry_run:
        table.add_row(ok(f"Pulling model {model}"), badge("DRY RUN", "mini.warn"))
        return

    ensure_model_disk_space(model, profiles, table)

    console.print(f"[mini.text]Pulling local model[/] [mini.blue]{model}[/] [mini.text]with Ollama...[/]")
    try:
        proc = subprocess.run(
            ["ollama", "pull", model],
            check=False,
            capture_output=True,
            text=True,
            timeout=MODEL_PULL_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        table.add_row(fail(f"Pulling model {model}"), badge("TIMEOUT", "mini.err"))
        console.print(table)
        console.print(
            Panel(
                "[mini.warn]Ollama model pull timed out.[/]\n"
                f"[mini.text]MiniDev waited {MODEL_PULL_TIMEOUT_SECONDS // 60} minutes for[/] "
                f"[mini.blue]{model}[/][mini.text]. Run the install command again; Ollama can usually resume "
                "partial downloads instead of starting over.[/]",
                border_style="mini.box",
                style=f"on {NAVY}",
                box=box.ROUNDED,
                padding=(1, 2),
            )
        )
        raise typer.Exit(2) from exc

    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout or "").strip()
        table.add_row(fail(f"Pulling model {model}"), badge("FAILED", "mini.err"))
        raise typer.BadParameter(message or f"Ollama failed to pull {model}.")

    manifest.record_model(ModelTouch(model, OLLAMA_MODEL_PROVIDER, "pull"))
    table.add_row(
        ok(f"Pulling model {model}"),
        badge("OK", "mini.ok"),
    )


def ensure_context_model(base_model: str, manifest: Manifest, table: Table, dry_run: bool) -> str:
    if base_model.startswith(MINIDEV_MODEL_PREFIX):
        manifest.record_model(ModelTouch(base_model, OLLAMA_MODEL_PROVIDER, "create"))
        table.add_row(ok("MiniDev agent model"), badge(base_model))
        return base_model

    model = context_model_name(base_model)
    if model_present(model):
        manifest.record_model(ModelTouch(model, OLLAMA_MODEL_PROVIDER, "create"))
        table.add_row(ok("MiniDev agent model"), badge(model))
        return model

    if dry_run:
        table.add_row(ok("Creating MiniDev agent model"), badge("DRY RUN", "mini.warn"))
        return model

    modelfile = f"FROM {base_model}\nPARAMETER num_ctx {MINIDEV_CONTEXT_TOKENS}\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        handle.write(modelfile)
        path = handle.name
    try:
        proc = subprocess.run(["ollama", "create", model, "-f", path], check=False, capture_output=True, text=True, timeout=180)
    finally:
        Path(path).unlink(missing_ok=True)

    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout or "").strip()
        table.add_row(fail("Creating MiniDev agent model"), badge("FAILED", "mini.err"))
        raise typer.BadParameter(message or f"Ollama failed to create {model}.")

    manifest.record_model(ModelTouch(model, OLLAMA_MODEL_PROVIDER, "create"))
    table.add_row(ok("Creating MiniDev agent model"), badge("OK", "mini.ok"))
    return model


def context_model_name(base_model: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", base_model).strip("-").lower()
    return f"{MINIDEV_MODEL_PREFIX}{normalized}-16k"


def ensure_model_disk_space(model: str, profiles: dict[str, object], table: Table) -> None:
    candidate = next((candidate for candidate in profiles.values() if candidate.model == model), None)
    if candidate is None:
        return

    free_gb = shutil.disk_usage(home_dir()).free / (1024**3)
    partial_gb = largest_ollama_partial_gb()
    remaining_model_gb = max(candidate.disk_gb - partial_gb, 0.5)
    required_gb = remaining_model_gb + MODEL_DISK_BUFFER_GB
    if free_gb >= required_gb:
        return

    table.add_row(fail(f"Disk space for {model}"), badge(f"{free_gb:.1f} GB FREE", "mini.err"))
    console.print(table)
    console.print(
        Panel(
            "[mini.warn]Not enough disk space for the selected local model.[/]\n"
            f"[mini.text]MiniDev needs about {required_gb:.1f} GB free to pull or resume[/] [mini.blue]{model}[/] "
            f"[mini.text]({candidate.disk_gb:.1f} GB model, {partial_gb:.1f} GB partial cache, plus safety buffer), but this device has "
            f"{free_gb:.1f} GB free.[/]\n"
            "[mini.text]Free space or choose a smaller profile, for example[/] "
            "[mini.blue]minidev install --profile medium[/][mini.text].[/]",
            border_style="mini.box",
            style=f"on {NAVY}",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )
    raise typer.Exit(2)


def largest_ollama_partial_gb() -> float:
    partials = (home_dir() / ".ollama" / "models" / "blobs").glob("*partial")
    sizes = [path.stat().st_size for path in partials if path.is_file()]
    if not sizes:
        return 0.0
    return max(sizes) / (1024**3)


def model_present(model: str) -> bool:
    try:
        proc = subprocess.run(["ollama", "list"], check=False, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return False
    if proc.returncode != 0:
        return False
    names = {line.split()[0] for line in proc.stdout.splitlines()[1:] if line.split()}
    if model in names:
        return True
    if ":" not in model and f"{model}:latest" in names:
        return True
    return False


def profile_pull_list(profiles: dict[str, object], selected_model: str, all_profiles: bool) -> list[str]:
    if not all_profiles:
        return [selected_model]
    models: list[str] = []
    for candidate in profiles.values():
        model = candidate.model
        if model not in models:
            models.append(model)
    if selected_model not in models:
        models.insert(0, selected_model)
    return models


def confirm_first_run_plan(models: list[str], profiles: dict[str, object], yes: bool, dry_run: bool) -> None:
    if yes or dry_run:
        return

    missing = [model for model in models if not model_present(model)]
    if not missing:
        return

    estimated = sum(model_disk_gb(model, profiles) for model in missing)
    free_gb = shutil.disk_usage(home_dir()).free / (1024**3)
    body = (
        "[mini.yellow]First-run download plan[/]\n"
        f"[mini.text]MiniDev will pull[/] [mini.blue]{', '.join(missing)}[/]\n"
        f"[mini.text]Estimated model storage:[/] [mini.yellow]{estimated:.1f} GB[/]\n"
        f"[mini.text]Free space now:[/] [mini.yellow]{free_gb:.1f} GB[/]\n\n"
        "[mini.text]MiniDev will also install or configure Ollama, OpenCode, and editor integration only when missing.[/]"
    )
    console.print(Panel(body, border_style="mini.box", style=f"on {NAVY}", box=box.ROUNDED, padding=(1, 2)))
    if not typer.confirm("Continue with this local-only MiniDev setup?", default=True):
        raise typer.Exit(1)


def model_disk_gb(model: str, profiles: dict[str, object]) -> float:
    for candidate in profiles.values():
        if getattr(candidate, "model", None) == model:
            return float(getattr(candidate, "disk_gb", 0.0))
    return 0.0


def check_model_tools(model: str, table: Table, dry_run: bool) -> bool:
    if dry_run:
        table.add_row(ok("Model tool calls"), badge("DRY RUN", "mini.warn"))
        return True
    result = check_structured_tool_calls(model)
    marker = ok("Model tool calls") if result.ok else warn("Model tool calls")
    table.add_row(marker, badge(result.detail, "mini.ok" if result.ok else "mini.warn"))
    if not result.ok:
        console.print(
            Panel(
                "[mini.yellow]Local model warning[/]\n"
                f"`{model}` can answer through Ollama, but it did not return structured tool calls. "
                "OpenCode chat may not be able to read/edit files with this model. "
                "Use `minidev install --model <tool-capable-model>` after choosing a local model with reliable tool support.",
                border_style="mini.box",
                style=f"on {NAVY}",
                box=box.ROUNDED,
                padding=(1, 2),
            )
        )
    return result.ok


def prune_missing_pulled_models(manifest: Manifest) -> None:
    models = manifest.data.get("models")
    if not isinstance(models, list):
        return
    kept: list[object] = []
    for item in models:
        if not isinstance(item, dict):
            kept.append(item)
            continue
        if item.get("provider") == OLLAMA_MODEL_PROVIDER and item.get("action") == "pull":
            name = str(item.get("name") or "")
            if name and not model_present(name):
                continue
        kept.append(item)
    manifest.data["models"] = kept


def write_config(
    config_path: Path,
    model: str,
    base_model: str,
    selected_profile: str,
    profiles: object,
    candidates: object,
    model_tools_ok: bool,
    system_info: object,
    ollama: CommandStatus,
    opencode: CommandStatus,
    editor_name: str,
    manifest: Manifest,
    table: Table,
    dry_run: bool,
) -> None:
    config = {
        "version": __version__,
        "installed_at": now_iso(),
        "model": model,
        "base_model": base_model,
        "provider": OLLAMA_MODEL_PROVIDER,
        "model_policy": {
            "local_only": True,
            "tool_calls": model_tools_ok,
            "mode": "agentic" if model_tools_ok else "chat_only",
            "context_tokens": MINIDEV_CONTEXT_TOKENS,
            "default_profile": selected_profile,
            "profiles": {profile: asdict(candidate) for profile, candidate in profiles.items()},
            "candidates": [asdict(candidate) for candidate in candidates],
        },
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
        "editor": {
            "name": editor_name,
            "configured": editor_name in {"vscode", "zed"},
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


def model_panel(model: str, ram_gb: float, candidates: object) -> Panel:
    candidate_lines = "\n".join(
        f"- {candidate.model} ({candidate.profile}, ~{candidate.disk_gb:g} GB)" for candidate in candidates
    )
    body = (
        f"[mini.yellow]MODEL SELECTED[/]\n"
        f"[mini.blue]{model}[/]\n\n"
        f"[mini.text]Best for your[/]\n"
        f"[mini.yellow]{ram_gb:g} GB RAM[/]\n\n"
        f"[mini.text]MiniDev local-only candidates[/]\n"
        f"[mini.blue]{candidate_lines}[/]"
    )
    return Panel(body, border_style=YELLOW, style=f"on {NAVY}", box=box.ROUNDED, padding=(1, 2))
