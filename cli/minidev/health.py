from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from rich import box
from rich.panel import Panel

from .console import NAVY, badge, console, ok, status_table, title_panel, warn
from .editor import opencode_config_present, vscode_extension_installed, zed_agent_config_present
from .install import ensure_ollama_ready, model_present, pull_model, run_install
from .manifest import Manifest
from .state import config_path, load_config, manifest_path
from .system import command_status


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str
    fixable: bool = False


def run_doctor(fix: bool = False) -> None:
    console.print(title_panel("MiniDev doctor"))
    config = load_config()
    manifest = Manifest(manifest_path())
    model = str(config.get("model") or "qwen2.5-coder:7b")

    checks = collect_checks(model)
    if fix and any(check.fixable and not check.ok for check in checks):
        run_fixes(model, manifest)
        checks = collect_checks(model)

    table = status_table("Doctor")
    for check in checks:
        marker = ok(check.name) if check.ok else warn(check.name)
        style = "mini.ok" if check.ok else "mini.warn"
        table.add_row(marker, badge(check.detail, style))

    console.print(table)
    healthy = all(check.ok for check in checks)
    status = "[mini.ok]Healthy[/]" if healthy else "[mini.warn]Needs attention[/]"
    console.print(Panel(status, border_style="mini.box", style=f"on {NAVY}", box=box.ROUNDED))


def run_status() -> None:
    config = load_config()
    model = str(config.get("model") or "unknown")
    table = status_table("MiniDev Status")

    server_running = ollama_running()
    table.add_row(
        ok("Server") if server_running else warn("Server"),
        badge("RUNNING" if server_running else "OFF", "mini.ok" if server_running else "mini.warn"),
    )
    loaded = model != "unknown" and model_present(model)
    table.add_row(
        ok("Model") if loaded else warn("Model"),
        badge(model if loaded else "NOT LOADED", "mini.ok" if loaded else "mini.warn"),
    )
    editor = editor_integration_status()
    table.add_row(
        ok("Editor") if editor.ok else warn("Editor"),
        badge(editor.detail, "mini.ok" if editor.ok else "mini.warn"),
    )
    lan = lan_status(config)
    table.add_row(
        ok("LAN") if lan == "ON" else warn("LAN"),
        badge(lan, "mini.ok" if lan == "ON" else "mini.warn"),
    )

    console.print(title_panel("minidev --status"))
    console.print(table)


def collect_checks(model: str) -> list[CheckResult]:
    ollama = command_status("ollama")
    opencode = command_status("opencode")
    editor = editor_integration_status()

    return [
        CheckResult("Ollama installed", ollama.working, ollama.version or "MISSING", fixable=True),
        CheckResult("Ollama running", ollama_running(), "RUNNING" if ollama_running() else "OFF", fixable=True),
        CheckResult("Model present", model_present(model), model, fixable=True),
        CheckResult("OpenCode installed", opencode.working, opencode.version or "MISSING", fixable=True),
        CheckResult("OpenCode configured", opencode_config_present(), "PERMISSIONS" if opencode_config_present() else "MISSING", fixable=True),
        CheckResult("Editor integration", editor.ok, editor.detail),
        CheckResult("Git repo detected", git_repo_detected(Path.cwd()), "YES" if git_repo_detected(Path.cwd()) else "NO"),
    ]


def run_fixes(model: str, manifest: Manifest) -> None:
    table = status_table("Fix")
    ollama = command_status("ollama")
    opencode = command_status("opencode")

    if not ollama.working or not opencode.working or not config_path().exists():
        run_install(model_override=model, repair=True, yes=True, dry_run=False)
        return

    if not ollama_running():
        ensure_ollama_ready(table, dry_run=False)

    if not model_present(model):
        pull_model(model, manifest, table, dry_run=False)
        manifest.save()

    if table.rows:
        console.print(table)


def ollama_running() -> bool:
    try:
        proc = subprocess.run(["ollama", "list"], check=False, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def editor_integration_status() -> CheckResult:
    if os.environ.get("MINIDEV_EDITOR_CONNECTED") in {"1", "true", "TRUE", "yes"}:
        return CheckResult("Editor integration", True, "CONNECTED")

    if vscode_extension_installed():
        return CheckResult("Editor integration", True, "VS CODE ACP")
    if zed_agent_config_present():
        return CheckResult("Editor integration", True, "ZED ACP")

    configured = configured_editor()
    if configured:
        return CheckResult("Editor integration", True, configured.upper())

    if command_status("code", ["--version"]).working:
        return CheckResult("Editor integration", True, "VS CODE")
    if command_status("zed", ["--version"]).working:
        return CheckResult("Editor integration", True, "ZED")
    return CheckResult("Editor integration", False, "NOT DETECTED")


def configured_editor() -> str | None:
    config = load_config()
    editor = config.get("editor")
    if isinstance(editor, dict):
        name = editor.get("name")
        if isinstance(name, str) and name:
            return name
    if isinstance(editor, str) and editor:
        return editor
    return None


def git_repo_detected(path: Path) -> bool:
    try:
        proc = subprocess.run(["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"], check=False, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def lan_status(config: dict[str, object]) -> str:
    lan = config.get("lan")
    if isinstance(lan, dict) and lan.get("enabled") is True:
        return "ON"
    host = os.environ.get("OLLAMA_HOST", "")
    if host and not host.startswith(("127.0.0.1", "localhost")):
        return "ON"
    return "OFF"
