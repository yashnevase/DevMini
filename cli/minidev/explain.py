from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer
from rich import box
from rich.markdown import Markdown
from rich.panel import Panel

from .benchmark import OLLAMA_GENERATE_URL
from .console import NAVY, badge, console, ok, status_table, title_panel, warn
from .project import DEV_DIR, relative, should_skip
from .state import load_config

MAX_CONTEXT_CHARS = 12000


@dataclass(frozen=True)
class Match:
    path: str
    kind: str
    name: str
    line: int
    snippet: str


@dataclass(frozen=True)
class ExplainContext:
    target: str
    match: Match
    source_excerpt: str
    callers: list[str]
    importers: list[str]


def run_explain(target: str, model_override: str | None = None) -> None:
    root = Path.cwd()
    index_path = root / DEV_DIR / "index.json"
    index = load_index(index_path)
    match = locate_target(root, index, target)
    context = build_explain_context(root, index, target, match)
    model = model_override or str(load_config().get("model") or "qwen2.5-coder:7b")

    console.print(title_panel("Explaining MiniDev target"))
    table = status_table("Explain")
    table.add_row(ok("Target"), badge(target))
    table.add_row(ok("Match"), badge(f"{match.path}:{match.line}"))
    table.add_row(ok("Model"), badge(model))
    table.add_row(ok("Callers"), badge(str(len(context.callers))))
    table.add_row(ok("Importers"), badge(str(len(context.importers))))
    console.print(table)

    explanation = explain_with_model(model, context)
    console.print(Panel(Markdown(explanation), border_style="mini.box", style=f"on {NAVY}", box=box.ROUNDED, padding=(1, 2)))


def load_index(index_path: Path) -> dict[str, Any]:
    if not index_path.exists():
        raise typer.BadParameter("No .devmini/index.json found. Run `minidev learn` first.")
    try:
        loaded = json.loads(index_path.read_text())
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(".devmini/index.json is not valid JSON. Run `minidev learn` again.") from exc
    if not isinstance(loaded, dict):
        raise typer.BadParameter(".devmini/index.json has an unexpected format. Run `minidev learn` again.")
    return loaded


def locate_target(root: Path, index: dict[str, Any], target: str) -> Match:
    files = index_files(index)
    target_path = root / target
    if target_path.exists() and target_path.is_file() and not should_skip(target_path, root):
        rel = relative(target_path, root)
        entry = next((item for item in files if item.get("path") == rel), None)
        first_symbol = first_symbol(entry) if entry else None
        if first_symbol:
            return symbol_match(rel, first_symbol)
        return Match(path=rel, kind="file", name=Path(rel).name, line=1, snippet=first_line(target_path))

    exact: list[Match] = []
    partial: list[Match] = []
    for item in files:
        path = item.get("path")
        if not isinstance(path, str):
            continue
        for symbol in symbols_for(item):
            name = str(symbol.get("name") or "")
            match = symbol_match(path, symbol)
            if name == target:
                exact.append(match)
            elif target.lower() in name.lower():
                partial.append(match)

    matches = exact or partial
    if not matches:
        raise typer.BadParameter(f"Could not find `{target}` in .devmini/index.json. Run `minidev learn` again if the index is stale.")
    if len(matches) > 1:
        choices = ", ".join(f"{item.name} at {item.path}:{item.line}" for item in matches[:5])
        raise typer.BadParameter(f"`{target}` matched multiple symbols: {choices}. Use a path or a more specific symbol.")
    return matches[0]


def build_explain_context(root: Path, index: dict[str, Any], target: str, match: Match) -> ExplainContext:
    source_path = root / match.path
    text = source_path.read_text(errors="replace") if source_path.exists() else ""
    excerpt = enclosing_excerpt(text, match.line)
    callers = direct_callers(root, index, match)
    importers = direct_importers(index, match)
    return ExplainContext(
        target=target,
        match=match,
        source_excerpt=excerpt[:MAX_CONTEXT_CHARS],
        callers=callers[:10],
        importers=importers[:10],
    )


def explain_with_model(model: str, context: ExplainContext) -> str:
    prompt = render_prompt(context)
    body = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": 500,
                "temperature": 0.1,
            },
        }
    ).encode("utf-8")
    request = urllib.request.Request(OLLAMA_GENERATE_URL, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            loaded = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise typer.BadParameter("Ollama is not reachable. Start it with `ollama serve` or run `minidev doctor --fix`.") from exc
    except json.JSONDecodeError as exc:
        raise typer.BadParameter("Ollama returned an invalid explanation response.") from exc
    if isinstance(loaded, dict) and isinstance(loaded.get("response"), str):
        return loaded["response"].strip()
    return "No explanation was returned by the model."


def render_prompt(context: ExplainContext) -> str:
    callers = "\n".join(f"- {item}" for item in context.callers) or "- None found in index/source scan."
    importers = "\n".join(f"- {item}" for item in context.importers) or "- None found in index."
    return f"""Explain this code target in plain language for a developer who is new to the project.

Target: {context.target}
Located at: {context.match.path}:{context.match.line}
Matched symbol: {context.match.name} ({context.match.kind})

Source excerpt:
```text
{context.source_excerpt}
```

Direct callers or references:
{callers}

Direct importers:
{importers}

Give:
1. What it does.
2. How data flows through it.
3. Who calls/imports it.
4. Risks or things to be careful with.
Keep the answer concise and concrete.
"""


def enclosing_excerpt(text: str, line: int, before: int = 3, after: int = 80) -> str:
    lines = text.splitlines()
    if not lines:
        return ""
    start = max(0, line - 1)
    definition_indent = indentation(lines[start])
    end = min(len(lines), start + after)
    for index in range(start + 1, min(len(lines), start + after)):
        stripped = lines[index].strip()
        if not stripped:
            continue
        if indentation(lines[index]) <= definition_indent and looks_like_definition(stripped):
            end = index
            break
    begin = max(0, start - before)
    numbered = [f"{idx + 1}: {lines[idx]}" for idx in range(begin, end)]
    return "\n".join(numbered)


def direct_callers(root: Path, index: dict[str, Any], match: Match) -> list[str]:
    if not match.name or match.kind == "file":
        return []
    pattern = re.compile(rf"\b{re.escape(match.name)}\s*\(")
    callers: list[str] = []
    for item in index_files(index):
        path = item.get("path")
        if not isinstance(path, str):
            continue
        source_path = root / path
        if not source_path.exists() or should_skip(source_path, root):
            continue
        for line_no, line in enumerate(source_path.read_text(errors="replace").splitlines(), start=1):
            if path == match.path and line_no == match.line:
                continue
            if pattern.search(line):
                callers.append(f"{path}:{line_no} {line.strip()[:140]}")
                break
    return callers


def direct_importers(index: dict[str, Any], match: Match) -> list[str]:
    module_stem = Path(match.path).stem
    importers: list[str] = []
    for item in index_files(index):
        path = item.get("path")
        if not isinstance(path, str) or path == match.path:
            continue
        for imported in imports_for(item):
            snippet = str(imported.get("snippet") or "")
            if module_stem in snippet or match.name in snippet:
                importers.append(f"{path}:{imported.get('line', 1)} {snippet[:140]}")
                break
    return importers


def index_files(index: dict[str, Any]) -> list[dict[str, Any]]:
    files = index.get("files")
    return [item for item in files if isinstance(item, dict)] if isinstance(files, list) else []


def symbols_for(item: dict[str, Any]) -> list[dict[str, Any]]:
    symbols = item.get("symbols")
    return [symbol for symbol in symbols if isinstance(symbol, dict)] if isinstance(symbols, list) else []


def imports_for(item: dict[str, Any]) -> list[dict[str, Any]]:
    imports = item.get("imports")
    return [imported for imported in imports if isinstance(imported, dict)] if isinstance(imports, list) else []


def first_symbol(entry: dict[str, Any] | None) -> dict[str, Any] | None:
    if not entry:
        return None
    symbols = symbols_for(entry)
    return symbols[0] if symbols else None


def symbol_match(path: str, symbol: dict[str, Any]) -> Match:
    return Match(
        path=path,
        kind=str(symbol.get("type") or "symbol"),
        name=str(symbol.get("name") or ""),
        line=int(symbol.get("line") or 1),
        snippet=str(symbol.get("snippet") or ""),
    )


def first_line(path: Path) -> str:
    try:
        return path.read_text(errors="replace").splitlines()[0][:160]
    except (OSError, IndexError):
        return ""


def indentation(line: str) -> int:
    return len(line) - len(line.lstrip())


def looks_like_definition(line: str) -> bool:
    return bool(re.match(r"(def|class|function|const|let|var|export|interface|type|struct|enum)\b", line))
