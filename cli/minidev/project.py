from __future__ import annotations

import json
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich import box
from rich.panel import Panel

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python < 3.11
    import tomli as tomllib

from .console import NAVY, badge, console, ok, status_table, title_panel, warn
from .manifest import FileTouch, Manifest
from .state import manifest_path

DEV_DIR = ".devmini"
DENY_PARTS = {".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__", ".mypy_cache", ".pytest_cache"}
DENY_NAMES = {".env", ".env.local", ".env.development", ".env.production", ".git/credentials"}
DENY_SUBSTRINGS = ("secret", "credential", "token")
DENY_SUFFIXES = (".key", ".pem", ".p12", ".pfx")

LANGUAGE_EXTENSIONS = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".rb": "Ruby",
    ".php": "PHP",
    ".c": "C",
    ".h": "C/C++",
    ".cc": "C++",
    ".cpp": "C++",
    ".cs": "C#",
    ".swift": "Swift",
    ".kt": "Kotlin",
}


@dataclass(frozen=True)
class ProjectFacts:
    root: Path
    package_manager: str
    languages: list[str]
    entry_points: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)


def run_init(force: bool = False) -> None:
    root = Path.cwd()
    facts = detect_project(root)
    dev_dir = root / DEV_DIR
    manifest = Manifest(manifest_path())

    console.print(title_panel("Initializing MiniDev project"))
    table = status_table("Project Init")
    table.add_row(ok("Project root"), badge(root.name or str(root)))
    table.add_row(ok("Package manager"), badge(facts.package_manager))
    table.add_row(ok("Languages"), badge(", ".join(facts.languages) or "UNKNOWN", "mini.yellow"))

    writes = {
        dev_dir / "project.md": render_project_md(facts),
        dev_dir / "environment.md": render_environment_md(facts),
        dev_dir / "conventions.md": render_conventions_md(facts),
        dev_dir / "decisions.md": "# Decisions\n\n- MiniDev initializes project context; OpenCode handles agent execution.\n",
        dev_dir / "bugs.md": "# Bugs\n\nNo known project-specific bugs recorded yet.\n",
        root / "AGENTS.md": render_agents_md(facts),
        root / "memory.md": render_memory_md(facts),
    }

    for path, content in writes.items():
        existed = path.exists()
        if existed and not force:
            table.add_row(warn(f"Skipping {path.name}"), badge("EXISTS", "mini.warn"))
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        manifest.record_file(FileTouch(str(path), "MiniDev project context", "overwrite" if existed else "create"))
        table.add_row(ok(f"Writing {relative(path, root)}"), badge("OK"))

    manifest.save()
    console.print(table)
    console.print(Panel("[mini.ok]Project context is ready.[/]", border_style="mini.box", style=f"on {NAVY}", box=box.ROUNDED))


def detect_project(root: Path) -> ProjectFacts:
    files = project_files(root, limit=5000)
    package_manager = detect_package_manager(root)
    languages = detect_languages(files)
    entry_points = detect_entry_points(root)
    frameworks = detect_frameworks(root)
    return ProjectFacts(root=root, package_manager=package_manager, languages=languages, entry_points=entry_points, frameworks=frameworks)


def project_files(root: Path, limit: int | None = None) -> list[Path]:
    paths: list[Path] = []
    try:
        proc = subprocess.run(["rg", "--files"], cwd=root, check=False, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        proc = None

    raw_paths = proc.stdout.splitlines() if proc and proc.returncode == 0 else [str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()]
    for raw in raw_paths:
        path = root / raw
        if should_skip(path, root):
            continue
        paths.append(path)
        if limit and len(paths) >= limit:
            break
    return paths


def should_skip(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return True
    parts = set(rel.parts)
    lowered = str(rel).lower()
    if parts & DENY_PARTS:
        return True
    if lowered in DENY_NAMES:
        return True
    if any(part.startswith(".env") for part in rel.parts):
        return True
    if any(text in lowered for text in DENY_SUBSTRINGS):
        return True
    return lowered.endswith(DENY_SUFFIXES)


def detect_package_manager(root: Path) -> str:
    markers = [
        ("pnpm-lock.yaml", "pnpm"),
        ("yarn.lock", "yarn"),
        ("package-lock.json", "npm"),
        ("bun.lockb", "bun"),
        ("bun.lock", "bun"),
        ("poetry.lock", "poetry"),
        ("uv.lock", "uv"),
        ("Pipfile.lock", "pipenv"),
        ("requirements.txt", "pip"),
        ("Cargo.lock", "cargo"),
        ("go.mod", "go"),
    ]
    for marker, manager in markers:
        if (root / marker).exists():
            return manager
    if (root / "package.json").exists():
        return "npm"
    if (root / "pyproject.toml").exists():
        return "pip"
    return "unknown"


def detect_languages(files: list[Path]) -> list[str]:
    counts: Counter[str] = Counter()
    for path in files:
        language = LANGUAGE_EXTENSIONS.get(path.suffix.lower())
        if language:
            counts[language] += 1
    return [name for name, _ in counts.most_common(5)]


def detect_entry_points(root: Path) -> list[str]:
    entries: list[str] = []
    package_json = root / "package.json"
    if package_json.exists() and not should_skip(package_json, root):
        try:
            package = json.loads(package_json.read_text())
            scripts = package.get("scripts", {})
            if isinstance(scripts, dict):
                entries.extend(f"npm run {name}" for name in sorted(scripts)[:8])
        except json.JSONDecodeError:
            pass

    pyproject = root / "pyproject.toml"
    if pyproject.exists() and not should_skip(pyproject, root):
        try:
            data = tomllib.loads(pyproject.read_text())
            scripts = data.get("project", {}).get("scripts", {})
            if isinstance(scripts, dict):
                entries.extend(sorted(scripts)[:8])
        except tomllib.TOMLDecodeError:
            pass

    for marker in ("main.py", "app.py", "manage.py"):
        if (root / marker).exists():
            entries.append(f"python {marker}")
    if (root / "go.mod").exists():
        entries.append("go run .")
    if (root / "Cargo.toml").exists():
        entries.append("cargo run")
    return dedupe(entries)


def detect_frameworks(root: Path) -> list[str]:
    frameworks: list[str] = []
    package_json = root / "package.json"
    if package_json.exists() and not should_skip(package_json, root):
        try:
            package = json.loads(package_json.read_text())
            deps: dict[str, Any] = {}
            for key in ("dependencies", "devDependencies"):
                value = package.get(key, {})
                if isinstance(value, dict):
                    deps.update(value)
            for name in ("react", "next", "vite", "svelte", "vue", "express"):
                if name in deps:
                    frameworks.append(name)
        except json.JSONDecodeError:
            pass
    return dedupe(frameworks)


def render_project_md(facts: ProjectFacts) -> str:
    return "\n".join(
        [
            "# Project",
            "",
            f"- Root: `{facts.root}`",
            f"- Package manager: `{facts.package_manager}`",
            f"- Languages: {comma_or_unknown(facts.languages)}",
            f"- Frameworks: {comma_or_none(facts.frameworks)}",
            "",
        ]
    )


def render_environment_md(facts: ProjectFacts) -> str:
    return "\n".join(
        [
            "# Environment",
            "",
            f"- Package manager: `{facts.package_manager}`",
            "- Install command: fill in after first successful setup.",
            "- Test command: fill in after first successful test run.",
            "",
            "## Entry Points",
            "",
            *[f"- `{entry}`" for entry in facts.entry_points],
            *([] if facts.entry_points else ["- Unknown"]),
            "",
        ]
    )


def render_conventions_md(facts: ProjectFacts) -> str:
    return "\n".join(
        [
            "# Conventions",
            "",
            "- Prefer existing project patterns over new abstractions.",
            "- Keep edits scoped to the requested behavior.",
            "- Do not read or store secrets, credentials, private keys, or `.env` contents.",
            f"- Primary languages detected: {comma_or_unknown(facts.languages)}.",
            "",
        ]
    )


def render_agents_md(facts: ProjectFacts) -> str:
    template = template_text("AGENTS.md")
    detected = "\n".join(
        [
            "",
            "## Detected Project Facts",
            "",
            f"- Package manager: `{facts.package_manager}`",
            f"- Languages: {comma_or_unknown(facts.languages)}",
            f"- Frameworks: {comma_or_none(facts.frameworks)}",
            "- Entry points:",
            *[f"  - `{entry}`" for entry in facts.entry_points],
            *([] if facts.entry_points else ["  - Unknown"]),
            "",
            "## MiniDev Boundary",
            "",
            "MiniDev generated this context. OpenCode handles runtime agent behavior, file edits, shell execution, and retrieval.",
            "",
        ]
    )
    return template.rstrip() + "\n" + detected


def render_memory_md(facts: ProjectFacts) -> str:
    return template_text("memory.md").rstrip() + "\n\n## Project Memory\n\n- Initialized by MiniDev.\n" + f"- Detected stack: {comma_or_unknown(facts.languages)} using `{facts.package_manager}`.\n"


def template_text(name: str) -> str:
    path = Path(__file__).resolve().parents[2] / "templates" / name
    return path.read_text()


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def comma_or_unknown(values: list[str]) -> str:
    return ", ".join(values) if values else "Unknown"


def comma_or_none(values: list[str]) -> str:
    return ", ".join(values) if values else "None detected"


def relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
