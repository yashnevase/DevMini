from minidev.project import detect_project, should_skip


def test_detect_project_finds_python_cli(tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "demo"

[project.scripts]
demo = "demo.cli:app"
"""
    )
    (tmp_path / "cli.py").write_text("def main(): pass\n")

    facts = detect_project(tmp_path)

    assert facts.package_manager == "pip"
    assert facts.languages == ["Python"]
    assert facts.entry_points == ["demo"]


def test_should_skip_secret_files(tmp_path) -> None:
    assert should_skip(tmp_path / ".env", tmp_path) is True
    assert should_skip(tmp_path / "api.secret.txt", tmp_path) is True
    assert should_skip(tmp_path / "private.key", tmp_path) is True
    assert should_skip(tmp_path / "src" / "app.py", tmp_path) is False
