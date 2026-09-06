from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer
from rich import box
from rich.panel import Panel

from .console import NAVY, badge, console, ok, status_table, title_panel, warn
from .manifest import FileTouch, Manifest
from .project import DEV_DIR, relative
from .state import manifest_path
from .study import MEMORY_FILE


@dataclass(frozen=True)
class CleanPlan:
    stale_index_paths: list[str]
    stale_memory_paths: list[str]
    memory_lines_removed: int


def run_clean(yes: bool = False) -> None:
    root = Path.cwd()
    index_path = root / DEV_DIR / "index.json"
    memory_path = root / MEMORY_FILE

    index = load_json_object(index_path)
    stale_index = stale_paths_from_index(root, index)
    stale_memory = stale_paths_from_memory(root, memory_path)
    stale = sorted(set(stale_index + stale_memory))
    lines_to_remove = memory_lines_with_paths(memory_path, stale)
    plan = CleanPlan(stale_index, stale_memory, len(lines_to_remove))

    console.print(title_panel("Cleaning MiniDev context"))
    table = status_table("Clean")
    table.add_row(ok("Index"), badge(relative(index_path, root) if index_path.exists() else "MISSING", "mini.ok" if index_path.exists() else "mini.warn"))
    table.add_row(ok("Memory"), badge(relative(memory_path, root) if memory_path.exists() else "MISSING", "mini.ok" if memory_path.exists() else "mini.warn"))
    table.add_row(warn("Stale index refs") if plan.stale_index_paths else ok("Stale index refs"), badge(str(len(plan.stale_index_paths)), "mini.warn" if plan.stale_index_paths else "mini.ok"))
    table.add_row(warn("Stale memory refs") if plan.stale_memory_paths else ok("Stale memory refs"), badge(str(len(plan.stale_memory_paths)), "mini.warn" if plan.stale_memory_paths else "mini.ok"))
    console.print(table)

    if stale:
        console.print(stale_panel(stale, plan.memory_lines_removed))
    else:
        console.print(Panel("[mini.ok]No stale MiniDev references found.[/]", border_style="mini.box", style=f"on {NAVY}", box=box.ROUNDED))
        return

    if not yes and not typer.confirm("Remove stale MiniDev references?", default=False):
        console.print(Panel("[mini.warn]Clean cancelled. No files changed.[/]", border_style="mini.box", style=f"on {NAVY}", box=box.ROUNDED))
        return

    touched: dict[Path, str] = {}
    if plan.stale_index_paths:
        write_pruned_index(index_path, index, set(plan.stale_index_paths))
        touched[index_path] = "write"
    if lines_to_remove:
        write_pruned_memory(memory_path, lines_to_remove)
        touched[memory_path] = "overwrite"

    manifest = Manifest(manifest_path())
    for path, action in touched.items():
        manifest.record_file(FileTouch(str(path), "MiniDev stale context cleanup", action))
    if touched:
        manifest.save()

    console.print(Panel("[mini.ok]Stale MiniDev references removed.[/]", border_style="mini.box", style=f"on {NAVY}", box=box.ROUNDED))


def stale_paths_from_index(root: Path, index: dict[str, Any]) -> list[str]:
    files = index.get("files")
    if not isinstance(files, list):
        return []
    stale: list[str] = []
    for item in files:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        if isinstance(path, str) and path and not (root / path).exists():
            stale.append(path)
    return sorted(set(stale))


def stale_paths_from_memory(root: Path, memory_path: Path) -> list[str]:
    if not memory_path.exists():
        return []
    existing_index_refs = set(extract_existing_index_paths(root))
    refs = extract_path_refs(memory_path.read_text(errors="replace"))
    return sorted(path for path in refs if should_treat_as_stale(root, path, existing_index_refs))


def extract_existing_index_paths(root: Path) -> list[str]:
    index = load_json_object(root / DEV_DIR / "index.json")
    files = index.get("files")
    if not isinstance(files, list):
        return []
    result: list[str] = []
    for item in files:
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            result.append(str(item["path"]))
    return result


def extract_path_refs(text: str) -> set[str]:
    refs: set[str] = set()
    for match in re.finditer(r"`([^`\n]+\.[A-Za-z0-9]{1,8})`", text):
        refs.add(match.group(1))
    for match in re.finditer(r"(?<![\w/.-])([A-Za-z0-9_./-]+/[A-Za-z0-9_./-]+\.[A-Za-z0-9]{1,8})(?![\w/.-])", text):
        refs.add(match.group(1))
    return {ref for ref in refs if not ref.startswith(("http://", "https://"))}


def should_treat_as_stale(root: Path, path: str, indexed_paths: set[str]) -> bool:
    if path not in indexed_paths and not ("/" in path or path.startswith(".")):
        return False
    return not (root / path).exists()


def memory_lines_with_paths(memory_path: Path, stale_paths: list[str]) -> set[int]:
    if not memory_path.exists() or not stale_paths:
        return set()
    lines = memory_path.read_text(errors="replace").splitlines()
    stale = set(stale_paths)
    remove: set[int] = set()
    for index, line in enumerate(lines):
        refs = extract_path_refs(line)
        if refs & stale or any(f"`{path}`" in line for path in stale):
            remove.add(index)
    return remove


def write_pruned_index(index_path: Path, index: dict[str, Any], stale_paths: set[str]) -> None:
    files = index.get("files")
    if isinstance(files, list):
        index["files"] = [item for item in files if not (isinstance(item, dict) and item.get("path") in stale_paths)]
    summary = index.get("summary")
    if isinstance(summary, dict):
        summary["files_seen"] = len(index.get("files", [])) if isinstance(index.get("files"), list) else 0
    index_path.write_text(json.dumps(index, indent=2) + "\n")


def write_pruned_memory(memory_path: Path, line_numbers: set[int]) -> None:
    lines = memory_path.read_text(errors="replace").splitlines()
    kept = [line for index, line in enumerate(lines) if index not in line_numbers]
    memory_path.write_text("\n".join(kept).rstrip() + "\n")


def load_json_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def stale_panel(paths: list[str], memory_lines_removed: int) -> Panel:
    body = "\n".join(
        [
            "[mini.yellow]Stale references[/]",
            *[f"- {path}" for path in paths],
            "",
            f"[mini.text]Memory lines to remove:[/] {memory_lines_removed}",
        ]
    )
    return Panel(body, border_style="mini.box", style=f"on {NAVY}", box=box.ROUNDED, padding=(1, 2))
