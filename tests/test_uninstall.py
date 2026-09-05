from pathlib import Path

from minidev.uninstall import safe_minidev_file


def test_safe_minidev_file_rejects_paths_outside_minidev(monkeypatch, tmp_path) -> None:
    home = tmp_path / "home"
    minidev_home = home / ".minidev"
    minidev_home.mkdir(parents=True)

    monkeypatch.setattr("minidev.uninstall.manifest_path", lambda: minidev_home / "manifest.json")

    assert safe_minidev_file(minidev_home / "config.json") is True
    assert safe_minidev_file(tmp_path / "project" / ".devmini" / "project.md") is True
    opencode_config = home / ".config" / "opencode" / "opencode.json"
    opencode_config.parent.mkdir(parents=True)
    opencode_config.write_text('{"minidev":{"permission_policy":"generated"}}')
    monkeypatch.setattr("minidev.uninstall.home_dir", lambda: home)
    assert safe_minidev_file(opencode_config) is True
    assert safe_minidev_file(home / "other.json") is False
    assert safe_minidev_file(Path("/tmp/not-minidev.json")) is False
