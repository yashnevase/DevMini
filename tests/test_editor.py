import json

from minidev.editor import MINIDEV_PERMISSION, merge_permissions, write_opencode_config, write_zed_agent_config, zed_available
from minidev.manifest import Manifest
from minidev.system import CommandStatus


def test_merge_permissions_preserves_existing_shell_rules() -> None:
    merged = merge_permissions(
        {
            "bash": {
                "make test": "allow",
                "rm *": "deny",
            },
            "question": "allow",
        },
        MINIDEV_PERMISSION,
    )

    assert merged["question"] == "allow"
    assert merged["bash"]["make test"] == "allow"
    assert merged["bash"]["rm *"] == "ask"
    assert merged["bash"]["rg *"] == "allow"
    assert merged["edit"] == "allow"


def test_write_opencode_config_records_overwrite(monkeypatch, tmp_path) -> None:
    home = tmp_path / "home"
    path = home / ".config" / "opencode" / "opencode.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"permission": {"question": "allow"}}))
    manifest = Manifest(home / ".minidev" / "manifest.json")

    monkeypatch.setattr("minidev.editor.home_dir", lambda: home)
    write_opencode_config(manifest, table=DummyTable(), model="qwen2.5-coder:14b")

    data = json.loads(path.read_text())
    assert data["permission"]["question"] == "allow"
    assert data["permission"]["bash"]["git commit*"] == "ask"
    assert data["model"] == "ollama/qwen2.5-coder:14b"
    assert data["small_model"] == "ollama/qwen2.5-coder:14b"
    assert data["provider"]["ollama"]["options"]["baseURL"] == "http://localhost:11434/v1"
    assert data["provider"]["ollama"]["models"]["qwen2.5-coder:14b"]["tool_call"] is True
    assert data["provider"]["ollama"]["models"]["qwen2.5-coder:14b"]["limit"]["context"] == 16384
    assert data["default_agent"] == "minidev"
    assert data["agent"]["build"]["model"] == "ollama/qwen2.5-coder:14b"
    assert "You are MiniDev" in data["agent"]["build"]["prompt"]
    assert data["agent"]["minidev"]["mode"] == "primary"
    assert manifest.data["files"][0]["action"] == "overwrite"


def test_write_opencode_config_can_disable_tool_calls(monkeypatch, tmp_path) -> None:
    home = tmp_path / "home"
    manifest = Manifest(home / ".minidev" / "manifest.json")

    monkeypatch.setattr("minidev.editor.home_dir", lambda: home)
    write_opencode_config(manifest, table=DummyTable(), model="qwen2.5-coder:14b", tool_calls=False)

    path = home / ".config" / "opencode" / "opencode.json"
    data = json.loads(path.read_text())
    assert data["provider"]["ollama"]["models"]["qwen2.5-coder:14b"]["tool_call"] is False
    assert data["agent"]["minidev"]["permission"]["read"] == "deny"


def test_write_zed_agent_config(monkeypatch, tmp_path) -> None:
    home = tmp_path / "home"
    manifest = Manifest(home / ".minidev" / "manifest.json")

    monkeypatch.setattr("minidev.editor.home_dir", lambda: home)
    monkeypatch.setattr("minidev.editor.minidev_command", lambda: "/Users/demo/.local/bin/minidev")
    write_zed_agent_config(manifest)

    path = home / ".config" / "zed" / "settings.json"
    data = json.loads(path.read_text())
    assert data["agent_servers"]["MiniDev"]["command"] == "/Users/demo/.local/bin/minidev"
    assert data["agent_servers"]["MiniDev"]["args"] == ["acp"]


def test_write_zed_agent_config_preserves_existing_settings(monkeypatch, tmp_path) -> None:
    home = tmp_path / "home"
    settings = home / ".config" / "zed" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(
        """
// Zed settings
{
  "ui_font_size": 16,
  "theme": {
    "dark": "One Dark",
  },
}
"""
    )
    manifest = Manifest(home / ".minidev" / "manifest.json")

    monkeypatch.setattr("minidev.editor.home_dir", lambda: home)
    monkeypatch.setattr("minidev.editor.minidev_command", lambda: "minidev")
    write_zed_agent_config(manifest)

    data = json.loads(settings.read_text())
    assert data["ui_font_size"] == 16
    assert data["theme"]["dark"] == "One Dark"
    assert data["agent_servers"]["MiniDev"]["args"] == ["acp"]


def test_zed_available_detects_app_bundle(monkeypatch, tmp_path) -> None:
    app = tmp_path / "Zed.app"
    app.mkdir()
    monkeypatch.setattr(
        "minidev.editor.command_status",
        lambda *args, **kwargs: CommandStatus("zed", None, None, installed=False, working=False),
    )
    monkeypatch.setattr("minidev.editor.zed_app_paths", lambda: [app])

    assert zed_available() is True


class DummyTable:
    def add_row(self, *args, **kwargs):
        pass
