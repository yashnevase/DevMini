import json

from minidev.learn import run_learn


def test_run_learn_writes_index(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("minidev.state.home_dir", lambda: tmp_path / "home")
    monkeypatch.setattr("minidev.project.home_dir", lambda: tmp_path / "home", raising=False)
    (tmp_path / "app.py").write_text("import os\n\nclass App:\n    pass\n\ndef main():\n    return os.getcwd()\n")

    run_learn(max_files=10)

    index_path = tmp_path / ".devmini" / "index.json"
    data = json.loads(index_path.read_text())
    assert data["summary"]["files_seen"] == 1
    assert data["files"][0]["path"] == "app.py"
    assert any(symbol["name"] in {"App", "main"} for symbol in data["files"][0]["symbols"])
