import json

from minidev.clean import memory_lines_with_paths, run_clean, stale_paths_from_index


def test_stale_paths_from_index(tmp_path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n")
    index = {
        "files": [
            {"path": "src/app.py"},
            {"path": "src/missing.py"},
            {"path": "LICENSE"},
        ]
    }

    assert stale_paths_from_index(tmp_path, index) == ["LICENSE", "src/missing.py"]


def test_memory_lines_with_stale_paths_handles_extensionless_names(tmp_path) -> None:
    memory = tmp_path / "memory.md"
    memory.write_text("- `LICENSE` changed 3 time(s)\n- `src/app.py` changed 1 time(s)\n")

    assert memory_lines_with_paths(memory, ["LICENSE"]) == {0}


def test_run_clean_prunes_index_and_memory(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / ".devmini").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("print('ok')\n")
    (tmp_path / ".devmini" / "index.json").write_text(
        json.dumps(
            {
                "summary": {"files_seen": 2},
                "files": [
                    {"path": "src/app.py"},
                    {"path": "src/old.py"},
                ],
            }
        )
    )
    (tmp_path / "memory.md").write_text("- Keep this\n- `src/old.py` changed 2 time(s)\n")

    run_clean(yes=True)

    index = json.loads((tmp_path / ".devmini" / "index.json").read_text())
    memory = (tmp_path / "memory.md").read_text()
    assert index["files"] == [{"path": "src/app.py"}]
    assert index["summary"]["files_seen"] == 1
    assert "src/old.py" not in memory
    assert "Keep this" in memory
