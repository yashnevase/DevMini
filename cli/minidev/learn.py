from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from rich import box
from rich.panel import Panel

from .console import NAVY, badge, console, ok, status_table, title_panel, warn
from .manifest import FileTouch, Manifest, now_iso
from .project import DEV_DIR, LANGUAGE_EXTENSIONS, project_files, relative
from .state import manifest_path

try:
    from tree_sitter_language_pack import get_parser
except ImportError:  # pragma: no cover - dependency exists in normal installs
    get_parser = None

TREE_SITTER_LANGUAGE_BY_EXT = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
}

SYMBOL_NODE_TYPES = {
    "function_definition",
    "class_definition",
    "method_definition",
    "function_declaration",
    "method_declaration",
    "class_declaration",
    "interface_declaration",
    "struct_item",
    "enum_item",
    "trait_item",
    "impl_item",
    "function_item",
    "lexical_declaration",
    "variable_declaration",
}

IMPORT_MARKERS = ("import", "package_clause", "use_declaration", "require")


def run_learn(max_files: int = 2000) -> None:
    root = Path.cwd()
    dev_dir = root / DEV_DIR
    index_path = dev_dir / "index.json"
    manifest = Manifest(manifest_path())

    console.print(title_panel("Learning project structure"))
    files = [path for path in project_files(root, limit=max_files) if path.suffix.lower() in TREE_SITTER_LANGUAGE_BY_EXT]
    entries: list[dict[str, Any]] = []
    language_counts: Counter[str] = Counter()
    parsed = 0

    for path in files:
        entry = index_file(path, root)
        entries.append(entry)
        if entry["language"]:
            language_counts[str(entry["language"])] += 1
        if entry["parsed"]:
            parsed += 1

    index = {
        "version": 1,
        "generated_at": now_iso(),
        "generator": "minidev learn",
        "root": str(root),
        "note": "MiniDev builds this lightweight index only. OpenCode handles retrieval during coding tasks.",
        "summary": {
            "files_seen": len(files),
            "files_parsed_with_tree_sitter": parsed,
            "languages": dict(language_counts.most_common()),
        },
        "files": entries,
    }

    dev_dir.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, indent=2) + "\n")
    manifest.record_file(FileTouch(str(index_path), "MiniDev symbol/import index", "write"))
    manifest.save()

    table = status_table("Learn")
    table.add_row(ok("Files indexed"), badge(str(len(files))))
    table.add_row(ok("Tree-sitter parsed"), badge(str(parsed)))
    table.add_row(ok("Index"), badge(relative(index_path, root)))
    if parsed < len(files):
        table.add_row(warn("Fallback/skipped parses"), badge(str(len(files) - parsed), "mini.warn"))
    console.print(table)
    console.print(Panel("[mini.ok]Index written.[/]", border_style="mini.box", style=f"on {NAVY}", box=box.ROUNDED))


def index_file(path: Path, root: Path) -> dict[str, Any]:
    language = TREE_SITTER_LANGUAGE_BY_EXT.get(path.suffix.lower())
    text = safe_read(path)
    if text is None or language is None:
        return file_entry(path, root, language, False, [], [])

    symbols: list[dict[str, Any]] = []
    imports: list[dict[str, Any]] = []
    parsed = False

    if get_parser is not None:
        try:
            parser = get_parser(language)
            tree = parser.parse(text.encode("utf-8"))
            walk_tree(tree.root_node, text.encode("utf-8"), symbols, imports)
            parsed = True
        except Exception:
            parsed = False

    return file_entry(path, root, language, parsed, symbols[:200], imports[:200])


def walk_tree(node, source: bytes, symbols: list[dict[str, Any]], imports: list[dict[str, Any]]) -> None:
    if node.type in SYMBOL_NODE_TYPES:
        symbols.append(node_payload(node, source))
    elif any(marker in node.type for marker in IMPORT_MARKERS):
        imports.append(node_payload(node, source))

    for child in node.children:
        walk_tree(child, source, symbols, imports)


def node_payload(node, source: bytes) -> dict[str, Any]:
    text = source[node.start_byte : node.end_byte].decode("utf-8", errors="replace").strip()
    return {
        "type": node.type,
        "name": symbol_name(node, source) or first_line(text),
        "line": node.start_point[0] + 1,
        "column": node.start_point[1] + 1,
        "snippet": first_line(text),
    }


def symbol_name(node, source: bytes) -> str | None:
    for child in node.children:
        if child.type in {"identifier", "type_identifier", "property_identifier"}:
            return source[child.start_byte : child.end_byte].decode("utf-8", errors="replace")
        nested = symbol_name(child, source)
        if nested:
            return nested
    return None


def file_entry(path: Path, root: Path, language: str | None, parsed: bool, symbols: list[dict[str, Any]], imports: list[dict[str, Any]]) -> dict[str, Any]:
    text = safe_read(path) or ""
    return {
        "path": relative(path, root),
        "language": language or LANGUAGE_EXTENSIONS.get(path.suffix.lower()),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "parsed": parsed,
        "symbols": symbols,
        "imports": imports,
    }


def safe_read(path: Path) -> str | None:
    try:
        return path.read_text(errors="replace")
    except OSError:
        return None


def first_line(text: str) -> str:
    return text.splitlines()[0][:160] if text.splitlines() else ""
