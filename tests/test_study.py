import json
import subprocess

from minidev.study import commits_since, run_study, safe_changed_files


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True)


def test_study_skips_denied_files_and_updates_state(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    git(tmp_path, "init")
    git(tmp_path, "config", "user.email", "test@example.com")
    git(tmp_path, "config", "user.name", "Tester")

    (tmp_path / "app.py").write_text("def main():\n    return 1\n")
    (tmp_path / ".env").write_text("SECRET=1\n")
    git(tmp_path, "add", "app.py", ".env")
    git(tmp_path, "commit", "-m", "fix startup bug")

    safe_files = safe_changed_files(tmp_path, "HEAD")
    assert "app.py" in safe_files
    assert ".env" not in safe_files

    run_study()

    state = json.loads((tmp_path / ".devmini" / "state.json").read_text())
    decisions = (tmp_path / ".devmini" / "decisions.md").read_text()
    memory = (tmp_path / "memory.md").read_text()

    assert state["last_studied_commit"]
    assert "app.py" in decisions
    assert ".env" not in decisions
    assert "bug fixes" in decisions
    assert "MiniDev Study" in memory

    assert commits_since(tmp_path, state["last_studied_commit"]) == []
