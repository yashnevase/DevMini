from minidev.project import detect_project, render_minidev_study_command, render_minidev_study_skill, render_project_opencode_json, should_skip, template_text


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


def test_template_text_reads_packaged_templates() -> None:
    assert "MiniDev prepares this file for OpenCode" in template_text("AGENTS.md")


def test_project_opencode_config_includes_minidev_memory_files() -> None:
    content = render_project_opencode_json()

    assert '"instructions"' in content
    assert '"memory.md"' in content
    assert '".devmini/decisions.md"' in content
    assert '"minidev-study"' in content
    assert "You are MiniDev" in content
    assert '"default_agent": "minidev"' in content


def test_minidev_command_and_skill_are_read_only() -> None:
    assert "Do not edit files" in render_minidev_study_command()
    assert "Do not edit files" in render_minidev_study_skill()
