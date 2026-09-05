from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer
from rich import box
from rich.panel import Panel

from .console import NAVY, badge, console, ok, status_table, title_panel, warn
from .manifest import FileTouch, Manifest, now_iso
from .project import DEV_DIR, relative, should_skip
from .state import manifest_path

STATE_FILE = "state.json"
DECISIONS_FILE = "decisions.md"
MEMORY_FILE = "memory.md"

PATTERN_KEYWORDS = {
    "tests": ("test", "spec", "pytest", "vitest", "jest", "unittest"),
    "bug fixes": ("fix", "bug", "regression", "crash", "broken", "error", "exception"),
    "refactors": ("refactor", "cleanup", "rename", "simplify", "extract"),
    "dependencies": ("dependency", "deps", "package", "lockfile", "requirements", "pyproject"),
    "configuration": ("config", "settings", "env", "ci", "workflow"),
    "typing": ("type", "typing", "mypy", "tsc", "interface"),
    "documentation": ("docs", "readme", "comment"),
}


@dataclass(frozen=True)
class CommitStudy:
    sha: str
    subject: str
    files: list[str]
    patterns: list[str]


def run_study() -> None:
    root = Path.cwd()
    if not git_repo_detected(root):
        raise typer.BadParameter("minidev study must be run inside a git repository.")

    dev_dir = root / DEV_DIR
    state_path = dev_dir / STATE_FILE
    state = load_state(state_path)
    last_seen = state.get("last_studied_commit")
    commits = commits_since(root, str(last_seen) if last_seen else None)
    head = git_stdout(root, ["rev-parse", "HEAD"]).strip()

    console.print(title_panel("Studying git history"))
    table = status_table("Study")
    table.add_row(ok("Repository"), badge(root.name or str(root)))
    table.add_row(ok("Last studied"), badge(short_sha(str(last_seen)) if last_seen else "FIRST RUN", "mini.yellow"))

    if not commits:
        table.add_row(warn("New commits"), badge("0", "mini.warn"))
        save_state(state_path, state | {"last_studied_commit": head, "last_studied_at": now_iso()})
        console.print(table)
        console.print(Panel("[mini.ok]Study state is current.[/]", border_style="mini.box", style=f"on {NAVY}", box=box.ROUNDED))
        return

    studies = [study_commit(root, sha) for sha in commits]
    summary = summarize_studies(studies, root)
    touched_files = append_study_summary(root, summary)

    manifest = Manifest(manifest_path())
    for path, action in touched_files.items():
        manifest.record_file(FileTouch(str(path), "MiniDev git history study", action))
    manifest.record_file(FileTouch(str(state_path), "MiniDev git study cursor", "write"))
    manifest.save()

    save_state(
        state_path,
        {
            **state,
            "last_studied_commit": head,
            "last_studied_at": now_iso(),
            "commits_studied_total": int(state.get("commits_studied_total", 0)) + len(commits),
        },
    )

    table.add_row(ok("New commits"), badge(str(len(commits))))
    table.add_row(ok("Hotspots"), badge(str(len(summary["hotspots"]))))
    table.add_row(ok("Patterns"), badge(str(len(summary["patterns"]))))
    table.add_row(ok("State"), badge(relative(state_path, root)))
    console.print(table)
    console.print(Panel("[mini.ok]Study summary appended.[/]", border_style="mini.box", style=f"on {NAVY}", box=box.ROUNDED))


def git_repo_detected(root: Path) -> bool:
    try:
        proc = subprocess.run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"], check=False, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def commits_since(root: Path, last_seen: str | None) -> list[str]:
    if last_seen and commit_is_ancestor(root, last_seen):
        range_spec = f"{last_seen}..HEAD"
        args = ["rev-list", "--reverse", range_spec]
    else:
        args = ["rev-list", "--reverse", "HEAD"]
    output = git_stdout(root, args)
    return [line.strip() for line in output.splitlines() if line.strip()]


def commit_is_ancestor(root: Path, sha: str) -> bool:
    try:
        proc = subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor", sha, "HEAD"], check=False, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0


def study_commit(root: Path, sha: str) -> CommitStudy:
    subject = git_stdout(root, ["log", "-1", "--format=%s", sha]).strip()
    files = safe_changed_files(root, sha)
    message = git_stdout(root, ["log", "-1", "--format=%s%n%b", sha])
    diff_text = safe_diff(root, sha, files)
    patterns = classify_patterns(message, diff_text, files)
    return CommitStudy(sha=sha, subject=subject, files=files, patterns=patterns)


def safe_changed_files(root: Path, sha: str) -> list[str]:
    output = git_stdout(root, ["diff-tree", "--root", "--no-commit-id", "--name-only", "-r", sha])
    safe: list[str] = []
    for raw in output.splitlines():
        path = root / raw.strip()
        if raw.strip() and not should_skip(path, root):
            safe.append(raw.strip())
    return safe


def safe_diff(root: Path, sha: str, files: list[str]) -> str:
    if not files:
        return ""
    return git_stdout(root, ["show", "--format=", "--unified=0", "--no-ext-diff", sha, "--", *files])


def classify_patterns(message: str, diff_text: str, files: list[str]) -> list[str]:
    haystack = " ".join([message, diff_text, " ".join(files)]).lower()
    patterns = [label for label, keywords in PATTERN_KEYWORDS.items() if any(keyword in haystack for keyword in keywords)]
    if any(path.startswith(("test/", "tests/")) or ".test." in path or "_test." in path for path in files):
        patterns.append("tests")
    return sorted(set(patterns))


def summarize_studies(studies: list[CommitStudy], root: Path) -> dict[str, Any]:
    file_counts: Counter[str] = Counter()
    pattern_counts: Counter[str] = Counter()
    subjects: list[str] = []

    for study in studies:
        file_counts.update(study.files)
        pattern_counts.update(study.patterns)
        if study.subject:
            subjects.append(study.subject)

    return {
        "generated_at": now_iso(),
        "commit_count": len(studies),
        "commit_range": {
            "first": studies[0].sha,
            "last": studies[-1].sha,
        },
        "hotspots": [{"path": path, "changes": count} for path, count in file_counts.most_common(10)],
        "patterns": [{"name": name, "count": count} for name, count in pattern_counts.most_common()],
        "subjects": subjects[:10],
        "root": str(root),
    }


def append_study_summary(root: Path, summary: dict[str, Any]) -> dict[Path, str]:
    dev_dir = root / DEV_DIR
    dev_dir.mkdir(parents=True, exist_ok=True)
    decisions_path = dev_dir / DECISIONS_FILE
    memory_path = root / MEMORY_FILE

    section = render_summary(summary)
    return {
        decisions_path: append_text(decisions_path, section),
        memory_path: append_text(memory_path, section),
    }


def render_summary(summary: dict[str, Any]) -> str:
    hotspots = summary["hotspots"] or [{"path": "None detected", "changes": 0}]
    patterns = summary["patterns"] or [{"name": "None detected", "count": 0}]
    subjects = summary["subjects"] or ["No commit subjects found."]
    lines = [
        "",
        f"## MiniDev Study - {summary['generated_at']}",
        "",
        f"- Commits studied: {summary['commit_count']}",
        f"- Commit range: `{short_sha(summary['commit_range']['first'])}` to `{short_sha(summary['commit_range']['last'])}`",
        "",
        "### Hotspots",
        "",
        *[f"- `{item['path']}` changed {item['changes']} time(s)" for item in hotspots],
        "",
        "### Recurring Patterns",
        "",
        *[f"- {item['name']}: {item['count']} commit(s)" for item in patterns],
        "",
        "### Recent Commit Themes",
        "",
        *[f"- {subject}" for subject in subjects],
        "",
    ]
    return "\n".join(lines)


def append_text(path: Path, text: str) -> str:
    existed = path.exists()
    existing = path.read_text(errors="replace") if existed else f"# {path.stem.title()}\n"
    path.write_text(existing.rstrip() + "\n" + text.lstrip())
    return "append" if existed else "create"


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n")


def git_stdout(root: Path, args: list[str]) -> str:
    proc = subprocess.run(["git", "-C", str(root), *args], check=False, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise typer.BadParameter(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout


def short_sha(sha: str) -> str:
    return re.sub(r"[^0-9a-fA-F]", "", sha)[:7] or "unknown"
