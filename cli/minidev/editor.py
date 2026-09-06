from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from rich import box
from rich.panel import Panel
from rich.table import Table

from .console import NAVY, badge, console, ok, warn
from .manifest import FileTouch, Manifest, PackageTouch
from .system import command_status, home_dir, run_command

VSCODE_ACP_EXTENSION = "formulahendry.acp-client"
ZED_AGENT_CONFIG = ".config/zed/settings.json"
OPENCODE_CONFIG = ".config/opencode/opencode.json"
OPENCODE_SCHEMA = "https://opencode.ai/config.json"
OLLAMA_PROVIDER_ID = "ollama"
MINIDEV_CONTEXT_TOKENS = 16384
MINIDEV_OUTPUT_TOKENS = 4096
MINIDEV_AGENT_PROMPT = (
    "You are MiniDev, a local offline coding assistant running through OpenCode and Ollama. "
    "Your name is MiniDev. If the user asks who you are or asks your name, answer that you are MiniDev. "
    "When the user asks who you are, say you are MiniDev. Be honest that OpenCode provides "
    "the editor/tool runtime and MiniDev provides installation, configuration, project memory, "
    "and local model routing. Always produce a visible final answer for the user. "
    "When you need file or project information, actually call the available structured tool; "
    "do not merely think about calling it. Never print fake JSON tool calls as normal chat text."
)
NO_TOOL_PERMISSION = {
    "read": "deny",
    "edit": "deny",
    "glob": "deny",
    "grep": "deny",
    "list": "deny",
    "bash": "deny",
    "task": "deny",
    "todowrite": "deny",
    "webfetch": "deny",
    "websearch": "deny",
    "lsp": "deny",
    "skill": "deny",
}

MINIDEV_PERMISSION = {
    "*": "ask",
    "read": "allow",
    "glob": "allow",
    "grep": "allow",
    "list": "allow",
    "lsp": "allow",
    "bash": {
        "*": "ask",
        "pwd": "allow",
        "ls*": "allow",
        "cat *": "allow",
        "sed *": "allow",
        "head *": "allow",
        "tail *": "allow",
        "wc *": "allow",
        "rg *": "allow",
        "grep *": "allow",
        "fd *": "allow",
        "find *": "allow",
        "git status*": "allow",
        "git diff*": "allow",
        "git log*": "allow",
        "git show*": "allow",
        "git branch*": "allow",
        "git rev-parse*": "allow",
        "pytest*": "allow",
        "python -m pytest*": "allow",
        "python3 -m pytest*": "allow",
        "npm test*": "allow",
        "npm run test*": "allow",
        "pnpm test*": "allow",
        "pnpm run test*": "allow",
        "yarn test*": "allow",
        "cargo test*": "allow",
        "go test*": "allow",
        "git commit*": "ask",
        "git tag*": "ask",
        "git push*": "ask",
        "npm install*": "ask",
        "pnpm install*": "ask",
        "yarn add*": "ask",
        "pip install*": "ask",
        "python -m pip install*": "ask",
        "python3 -m pip install*": "ask",
        "brew install*": "ask",
        "brew uninstall*": "ask",
        "rm *": "ask",
        "rmdir *": "ask",
        "unlink *": "ask",
        "trash *": "ask",
    },
    "edit": "allow",
    "webfetch": "allow",
}


def configure_editor_and_opencode(
    manifest: Manifest,
    table: Table,
    dry_run: bool = False,
    model: str | None = None,
    tool_calls: bool = True,
) -> str:
    write_opencode_config(manifest, table, dry_run=dry_run, model=model, tool_calls=tool_calls)
    return configure_editor(manifest, table, dry_run=dry_run)


def configure_editor(manifest: Manifest, table: Table, dry_run: bool = False) -> str:
    code = command_status("code", ["--version"])
    if code.working:
        if vscode_extension_installed():
            manifest.record_package(PackageTouch(VSCODE_ACP_EXTENSION, "vscode", "present"))
            table.add_row(ok("VS Code ACP extension"), badge("PRESENT"))
        else:
            run_command(["code", "--install-extension", VSCODE_ACP_EXTENSION], dry_run=dry_run)
            manifest.record_package(PackageTouch(VSCODE_ACP_EXTENSION, "vscode", "install"))
            table.add_row(ok("VS Code ACP extension"), badge("DRY RUN" if dry_run else "OK", "mini.warn" if dry_run else "mini.ok"))
        return "vscode"

    if zed_available():
        write_zed_agent_config(manifest, dry_run=dry_run)
        table.add_row(ok("Zed agent config"), badge("DRY RUN" if dry_run else "OK", "mini.warn" if dry_run else "mini.ok"))
        return "zed"

    table.add_row(warn("Editor integration"), badge("MANUAL", "mini.warn"))
    console.print(manual_editor_panel())
    return "manual"


def write_zed_agent_config(manifest: Manifest, dry_run: bool = False) -> Path:
    path = home_dir() / ZED_AGENT_CONFIG
    existed = path.exists()
    content = load_jsonc_object(path)
    agent_servers = content.get("agent_servers") if isinstance(content.get("agent_servers"), dict) else {}
    agent_servers["MiniDev"] = {
        "type": "custom",
        "command": minidev_command(),
        "args": ["acp"],
    }
    content["agent_servers"] = agent_servers
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content, indent=2) + "\n")
    manifest.record_file(FileTouch(str(path), "Zed ACP settings for MiniDev", "overwrite" if existed else "create"))
    return path


def write_opencode_config(
    manifest: Manifest,
    table: Table,
    dry_run: bool = False,
    model: str | None = None,
    tool_calls: bool = True,
) -> Path:
    path = opencode_config_path()
    existed = path.exists()
    config = load_json_object(path)
    config["$schema"] = config.get("$schema") or OPENCODE_SCHEMA
    config.pop("minidev", None)
    config["permission"] = merge_permissions(config.get("permission"), MINIDEV_PERMISSION)
    if model:
        configure_ollama_provider(config, model, tool_calls=tool_calls)

    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config, indent=2) + "\n")
    manifest.record_file(FileTouch(str(path), "OpenCode permission policy generated by MiniDev", "overwrite" if existed else "create"))
    table.add_row(ok("OpenCode permissions"), badge("DRY RUN" if dry_run else "OK", "mini.warn" if dry_run else "mini.ok"))
    return path


def opencode_config_path() -> Path:
    return home_dir() / OPENCODE_CONFIG


def opencode_config_present(model: str | None = None) -> bool:
    path = opencode_config_path()
    config = load_json_object(path)
    if not path.exists() or config.get("permission") is None:
        return False
    if model is None:
        return True
    model_ref = ollama_model_ref(model)
    provider = config.get("provider")
    return config.get("model") == model_ref and isinstance(provider, dict) and OLLAMA_PROVIDER_ID in provider


def vscode_extension_installed() -> bool:
    code = command_status("code", ["--version"])
    if not code.working:
        return False
    try:
        proc = subprocess.run(["code", "--list-extensions"], check=False, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    extensions = {line.strip().lower() for line in proc.stdout.splitlines()}
    return VSCODE_ACP_EXTENSION.lower() in extensions


def zed_agent_config_present() -> bool:
    config = load_jsonc_object(home_dir() / ZED_AGENT_CONFIG)
    agent_servers = config.get("agent_servers")
    return isinstance(agent_servers, dict) and "MiniDev" in agent_servers


def load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def load_jsonc_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        text = strip_jsonc(path.read_text())
        loaded = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def strip_jsonc(text: str) -> str:
    output: list[str] = []
    in_string = False
    escape = False
    index = 0
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if in_string:
            output.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue
        if char == "/" and next_char == "/":
            index += 2
            while index < len(text) and text[index] not in "\r\n":
                index += 1
            continue
        if char == "/" and next_char == "*":
            index += 2
            while index + 1 < len(text) and not (text[index] == "*" and text[index + 1] == "/"):
                index += 1
            index += 2
            continue
        output.append(char)
        index += 1
    return re.sub(r",\s*([}\]])", r"\1", "".join(output))


def merge_permissions(existing: object, desired: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(existing, dict):
        existing = {}
    merged = dict(existing)
    for key, value in desired.items():
        old_value = merged.get(key)
        if isinstance(value, dict) and isinstance(old_value, dict):
            merged[key] = {**old_value, **value}
        else:
            merged[key] = value
    return merged


def configure_ollama_provider(config: dict[str, Any], model: str, tool_calls: bool = True) -> None:
    model_ref = ollama_model_ref(model)
    provider = config.get("provider") if isinstance(config.get("provider"), dict) else {}
    ollama = provider.get(OLLAMA_PROVIDER_ID) if isinstance(provider.get(OLLAMA_PROVIDER_ID), dict) else {}
    options = ollama.get("options") if isinstance(ollama.get("options"), dict) else {}
    existing_models = ollama.get("models") if isinstance(ollama.get("models"), dict) else {}
    existing_model_config = existing_models.get(model) if isinstance(existing_models.get(model), dict) else {}
    models = {}
    models[model] = {
        **existing_model_config,
        "name": f"MiniDev Local {model}",
        "reasoning": False,
        "tool_call": tool_calls,
        "limit": {
            "context": MINIDEV_CONTEXT_TOKENS,
            "output": MINIDEV_OUTPUT_TOKENS,
        },
    }
    provider[OLLAMA_PROVIDER_ID] = {
        **ollama,
        "npm": "@ai-sdk/openai-compatible",
        "name": "MiniDev Ollama",
        "options": {
            **options,
            "baseURL": "http://localhost:11434/v1",
        },
        "models": models,
    }
    config["provider"] = provider
    config["model"] = model_ref
    config["small_model"] = model_ref
    config["default_agent"] = "minidev"
    config["agent"] = configure_agents(config.get("agent"), model_ref, tool_calls=tool_calls)


def configure_agents(existing: object, model_ref: str, tool_calls: bool = True) -> dict[str, Any]:
    agents = dict(existing) if isinstance(existing, dict) else {}
    for name in ("build", "plan", "general", "explore"):
        current = agents.get(name) if isinstance(agents.get(name), dict) else {}
        agents[name] = {**current, "model": model_ref, "prompt": MINIDEV_AGENT_PROMPT}
    current = agents.get("minidev") if isinstance(agents.get("minidev"), dict) else {}
    agents["minidev"] = {
        **current,
        "model": model_ref,
        "mode": "primary",
        "description": "MiniDev local offline assistant",
        "prompt": MINIDEV_AGENT_PROMPT,
        "permission": MINIDEV_PERMISSION if tool_calls else NO_TOOL_PERMISSION,
    }
    return agents


def ollama_model_ref(model: str) -> str:
    return f"{OLLAMA_PROVIDER_ID}/{model}"


def zed_available() -> bool:
    if command_status("zed", ["--version"]).working:
        return True
    return any(path.exists() for path in zed_app_paths())


def zed_app_paths() -> list[Path]:
    return [Path("/Applications/Zed.app"), home_dir() / "Applications" / "Zed.app"]


def opencode_command() -> str:
    status = command_status("opencode")
    return status.path or "opencode"


def minidev_command() -> str:
    status = command_status("minidev")
    return status.path or "minidev"


def manual_editor_panel() -> Panel:
    body = (
        "[mini.yellow]Manual editor setup[/]\n"
        "VS Code: install the ACP Client extension, then connect it to `opencode acp`.\n"
        "Zed: add an External Agent named MiniDev with command `opencode` and args `[\"acp\"]`."
    )
    return Panel(body, border_style="mini.box", style=f"on {NAVY}", box=box.ROUNDED, padding=(1, 2))
