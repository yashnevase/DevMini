from __future__ import annotations

import subprocess
from pathlib import Path

import typer

from .editor import MINIDEV_AGENT_PROMPT, ollama_model_ref
from .model_catalog import AUTO, MAX, PROFILES
from .state import load_config
from .system import command_status

OPENCODE_OPTIONS_WITH_VALUES = {
    "--command",
    "--session",
    "-s",
    "--format",
    "--file",
    "-f",
    "--title",
    "--attach",
    "--password",
    "-p",
    "--username",
    "-u",
    "--dir",
    "--port",
    "--variant",
    "--log-level",
}


def run_chat(args: list[str]) -> None:
    profile, checked_args = extract_profile_arg(args)
    model = configured_local_model(profile=profile)
    model_override, checked_args = extract_local_model_arg(checked_args)
    if model_override:
        model = model_override
    checked_args = enforce_agent_args(checked_args)
    command = ["opencode", "--agent", "minidev", "--model", model, *checked_args]
    opencode_args, message_args = split_run_args(checked_args)
    if message_args:
        command = ["opencode", "run", "--agent", "minidev", "--model", model, *opencode_args, minidev_prompt(message_args)]
    run_opencode(command)


def run_acp(args: list[str]) -> None:
    command = ["opencode", "acp", "--cwd", str(Path.cwd()), *args]
    run_opencode(command)


def run_opencode(command: list[str]) -> None:
    status = command_status("opencode")
    if not status.working:
        raise typer.BadParameter("OpenCode is not installed or not working. Run `minidev install` first.")
    raise typer.Exit(subprocess.call(command))


def minidev_prompt(args: list[str]) -> str:
    user_message = " ".join(args)
    return f"{MINIDEV_AGENT_PROMPT}\n\nUser request:\n{user_message}"


def split_run_args(args: list[str]) -> tuple[list[str], list[str]]:
    opencode_args: list[str] = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--":
            return opencode_args, args[index + 1 :]
        if not arg.startswith("-"):
            return opencode_args, args[index:]
        opencode_args.append(arg)
        if arg in OPENCODE_OPTIONS_WITH_VALUES and index + 1 < len(args):
            opencode_args.append(args[index + 1])
            index += 2
            continue
        index += 1
    return opencode_args, []


def configured_local_model(profile: str = AUTO) -> str:
    config = load_config()
    if profile != AUTO:
        model = configured_profile_model(config, profile)
        return ollama_model_ref(model)
    model = config.get("model")
    if not isinstance(model, str) or not model:
        raise typer.BadParameter("No MiniDev local model is configured. Run `minidev install` first.")
    return ollama_model_ref(model)


def configured_profile_model(config: dict[str, object], profile: str) -> str:
    normalized = profile.lower()
    if normalized == AUTO:
        normalized = MAX
    if normalized not in PROFILES:
        raise typer.BadParameter("Profile must be one of: low, medium, max.")
    policy = config.get("model_policy")
    profiles = policy.get("profiles") if isinstance(policy, dict) else None
    selected = profiles.get(normalized) if isinstance(profiles, dict) else None
    model = selected.get("model") if isinstance(selected, dict) else None
    if not isinstance(model, str) or not model:
        raise typer.BadParameter(f"No MiniDev `{normalized}` model is configured. Run `minidev install --all-profiles`.")
    return model


def extract_profile_arg(args: list[str]) -> tuple[str, list[str]]:
    cleaned: list[str] = []
    profile = AUTO
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--profile":
            if index + 1 >= len(args):
                raise typer.BadParameter("Missing value for --profile.")
            profile = args[index + 1]
            index += 2
            continue
        if arg.startswith("--profile="):
            profile = arg.split("=", 1)[1]
            index += 1
            continue
        cleaned.append(arg)
        index += 1
    return profile, cleaned


def enforce_local_model_args(args: list[str]) -> list[str]:
    _, cleaned = extract_local_model_arg(args)
    return enforce_agent_args(cleaned)


def extract_local_model_arg(args: list[str]) -> tuple[str | None, list[str]]:
    cleaned: list[str] = []
    model: str | None = None
    index = 0
    while index < len(args):
        arg = args[index]
        if arg in {"--model", "-m"}:
            if index + 1 >= len(args):
                raise typer.BadParameter("Missing value for --model.")
            requested = args[index + 1]
            if not requested.startswith("ollama/"):
                raise typer.BadParameter("MiniDev chat is local-only. Use an Ollama model such as `ollama/qwen3:30b-a3b`.")
            model = requested
            index += 2
            continue
        if arg.startswith("--model="):
            requested = arg.split("=", 1)[1]
            if not requested.startswith("ollama/"):
                raise typer.BadParameter("MiniDev chat is local-only. Use an Ollama model such as `ollama/qwen3:30b-a3b`.")
            model = requested
            index += 1
            continue
        cleaned.append(arg)
        index += 1
    return model, cleaned


def enforce_agent_args(args: list[str]) -> list[str]:
    cleaned: list[str] = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--agent":
            if index + 1 >= len(args):
                raise typer.BadParameter("Missing value for --agent.")
            requested = args[index + 1]
            if requested != "minidev":
                raise typer.BadParameter("MiniDev chat always uses the `minidev` agent.")
            index += 2
            continue
        if arg.startswith("--agent="):
            requested = arg.split("=", 1)[1]
            if requested != "minidev":
                raise typer.BadParameter("MiniDev chat always uses the `minidev` agent.")
            index += 1
            continue
        cleaned.append(arg)
        index += 1
    return cleaned
