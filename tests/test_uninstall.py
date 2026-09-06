from pathlib import Path

from minidev.manifest import Manifest
from minidev.uninstall import remove_models, safe_minidev_file


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
    zed_settings = home / ".config" / "zed" / "settings.json"
    zed_settings.parent.mkdir(parents=True)
    zed_settings.write_text('{"agent_servers":{"MiniDev":{"command":"minidev"}}}')
    monkeypatch.setattr("minidev.uninstall.home_dir", lambda: home)
    assert safe_minidev_file(opencode_config) is True
    assert safe_minidev_file(zed_settings) is True
    assert safe_minidev_file(home / "other.json") is False
    assert safe_minidev_file(Path("/tmp/not-minidev.json")) is False


def test_remove_models_removes_created_and_pulled_models(monkeypatch, tmp_path) -> None:
    manifest = Manifest(tmp_path / "manifest.json")
    manifest.data["models"] = [
        {"name": "base", "provider": "ollama", "action": "pull"},
        {"name": "alias", "provider": "ollama", "action": "create"},
        {"name": "user-owned", "provider": "ollama", "action": "present"},
    ]
    calls = []

    monkeypatch.setattr("minidev.uninstall.model_present", lambda name: True)
    monkeypatch.setattr("minidev.uninstall.run_command", lambda command, dry_run=False: calls.append(command))

    remove_models(manifest, DummyTable(), dry_run=False)

    assert calls == [["ollama", "rm", "base"], ["ollama", "rm", "alias"]]


def test_remove_models_skips_missing_models(monkeypatch, tmp_path) -> None:
    manifest = Manifest(tmp_path / "manifest.json")
    manifest.data["models"] = [{"name": "gone", "provider": "ollama", "action": "pull"}]
    calls = []

    monkeypatch.setattr("minidev.uninstall.model_present", lambda name: False)
    monkeypatch.setattr("minidev.uninstall.run_command", lambda command, dry_run=False: calls.append(command))

    remove_models(manifest, DummyTable(), dry_run=False)

    assert calls == []


class DummyTable:
    def add_row(self, *args, **kwargs):
        pass
