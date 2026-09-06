import pytest

from minidev.explain import build_explain_context, enclosing_excerpt, locate_target, render_prompt


def test_locate_target_finds_symbol(tmp_path) -> None:
    index = {
        "files": [
            {
                "path": "app.py",
                "symbols": [{"type": "function_definition", "name": "main", "line": 3, "snippet": "def main():"}],
                "imports": [],
            }
        ]
    }

    match = locate_target(tmp_path, index, "main")

    assert match.path == "app.py"
    assert match.line == 3


def test_locate_target_rejects_ambiguous_symbols(tmp_path) -> None:
    index = {
        "files": [
            {"path": "a.py", "symbols": [{"name": "main", "line": 1}], "imports": []},
            {"path": "b.py", "symbols": [{"name": "main", "line": 1}], "imports": []},
        ]
    }

    with pytest.raises(Exception):
        locate_target(tmp_path, index, "main")


def test_build_explain_context_collects_callers_and_importers(tmp_path) -> None:
    (tmp_path / "app.py").write_text("def helper():\n    return 1\n\ndef main():\n    return helper()\n")
    (tmp_path / "other.py").write_text("from app import helper\n\nvalue = helper()\n")
    index = {
        "files": [
            {
                "path": "app.py",
                "symbols": [{"type": "function_definition", "name": "helper", "line": 1, "snippet": "def helper():"}],
                "imports": [],
            },
            {
                "path": "other.py",
                "symbols": [],
                "imports": [{"line": 1, "snippet": "from app import helper"}],
            },
        ]
    }
    match = locate_target(tmp_path, index, "helper")

    context = build_explain_context(tmp_path, index, "helper", match)

    assert "def helper" in context.source_excerpt
    assert any("app.py:5" in caller for caller in context.callers)
    assert any("other.py:1" in importer for importer in context.importers)


def test_enclosing_excerpt_stops_at_next_definition() -> None:
    text = "def first():\n    return 1\n\ndef second():\n    return 2\n"

    excerpt = enclosing_excerpt(text, 1)

    assert "def first" in excerpt
    assert "def second" not in excerpt


def test_render_prompt_contains_context() -> None:
    context = type(
        "Context",
        (),
        {
            "target": "main",
            "match": type("Match", (), {"path": "app.py", "line": 1, "name": "main", "kind": "function_definition"})(),
            "source_excerpt": "1: def main():",
            "callers": ["other.py:2 main()"],
            "importers": ["other.py:1 from app import main"],
        },
    )()

    prompt = render_prompt(context)

    assert "Explain this code target" in prompt
    assert "other.py:2 main()" in prompt
    assert "from app import main" in prompt
